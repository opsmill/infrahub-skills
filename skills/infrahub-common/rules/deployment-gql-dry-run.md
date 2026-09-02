---
title: Dry-Run GraphQL Queries Against the Live Schema Before Merge
impact: HIGH
tags: deployment, gql, validation, dry-run, schema-sync, pre-merge
---

## Dry-Run GraphQL Queries Against the Live Schema Before Merge

**Impact:** HIGH

YAML schema validation (`infrahubctl schema check`) and Python
type checking catch lots of mistakes, but they **don't catch
GraphQL query/schema mismatches**. A query that asks for a
field that doesn't exist on a type — or asks for a field on
a union type without inline fragments — passes every static
check, and only fails when `CoreRepository` actually executes
the query during schema-sync.

When a `.gql` file under `queries/**/` is wrong, the typical
failure shape is:

- `CoreRepository` sync hangs in `error-import` state
- Zero generator / transform / check definitions register
- Downstream pipelines (`invoke init`, proposed-change
  validation) time out with no obvious root cause

This is a *silent* failure from the developer's perspective —
the YAML is fine, the Python is fine, the only signal is that
nothing runs.

### The rule

Before opening a PR that touches any `.gql` file under
`queries/**/`, run each affected query against a live
Infrahub schema.

**Which command depends on how the transform is
registered.** `render` serves `jinja2_transforms`
only, and `transform` serves `python_transforms`
only. Reaching for the wrong one prints
"Unable to find \<name\> in repository config file",
which reads like the transform is unregistered rather
than like the wrong command, so it is easy to conclude
the dry-run is unavailable and skip the gate entirely.

```bash
# Python transform, registered under python_transforms
infrahubctl transform <name> <param>=<value> --branch <branch>

# Jinja2 transform, registered under jinja2_transforms
infrahubctl render <name> <param>=<value> --branch <branch>

# For a check or generator, the equivalent is to run the
# check/generator itself locally — it will fetch via the .gql
# and surface any GraphQL error on the spot. Both take the
# name as a positional argument; there is no `run` subcommand.
infrahubctl check <check_name> --branch <branch>
infrahubctl generator <generator_name> <param>=<target_id> --branch <branch>
```

Two details that each cost a round trip:

- **A required query variable has to be supplied by
  hand locally.** In the pipeline the artifact
  definition binds it from an attribute on the target,
  so a local invocation is the only place a human ever
  types it. Omitting it fails inside the query rather
  than at the CLI, which looks like a query bug.
- **A generator target is a query variable, not a
  bare id.** Everything after the generator name is
  parsed as `key=value`; a token with no `=` is dropped
  without a warning, so the generator runs with no
  variables and the failure looks like a query bug.
- **Neither transform command reaches a check or a
  generator.** Those are dry-run by running the check
  or the generator itself, as above.

If your local Infrahub doesn't have data matching the query,
spin up a fresh instance with the bootstrap dataset
(`invoke init` or equivalent) so the query exercises real
shapes — empty datasets hide union-fragment bugs because no
concrete instance is returned to fail on.

### What this catches that YAML-check misses

| Failure | Caught by YAML check? | Caught by dry-run? |
| ------- | --------------------- | ------------------ |
| `kind:` typo in schema | Yes | Yes |
| Indentation / structure error | Yes | Yes |
| `human_friendly_id` referencing missing attr | Yes | Yes |
| Querying a field that doesn't exist on the target type | No | Yes |
| Querying a field on a union without inline fragments (and the union contains an inheritor that lacks the field) | No | Yes |
| Filter argument typo | No | Yes |

The two non-caught cases are the most common silent-failure
sources in production schema-sync.

### When to skip

Trivial query edits that only adjust whitespace, comments, or
the order of explicitly-selected scalar fields don't need a
dry-run. Any change to a field selection, a filter argument,
a fragment, or a relationship traversal does.

### CI integration

Where practical, wire the dry-run into CI as a
pre-merge gate on `queries/**/*.gql` changes, using
`infrahubctl transform` for each `python_transforms`
entry and `infrahubctl render` for each
`jinja2_transforms` entry. The check takes <1s per
query against a warmed Infrahub and prevents the
silent-sync-failure class of bug from reaching main.

Reference:
[Infrahub schema docs](https://docs.infrahub.app)
