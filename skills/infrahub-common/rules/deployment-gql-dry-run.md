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

```bash
# Per-query dry-run: rendering executes the transform's query
# against the branch and surfaces any GraphQL/schema mismatch
infrahubctl render <transform_name> --branch <branch>

# For a check or generator, the equivalent is to run the
# check/generator itself locally — it will fetch via the .gql
# and surface any GraphQL error on the spot
infrahubctl check run <check_name>
infrahubctl generator run <generator_name> <target_id>
```

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

Where practical, wire `infrahubctl render --branch <ci-branch>` into CI
as a pre-merge gate on `queries/**/*.gql` changes. The check
takes <1s per query against a warmed Infrahub and prevents
the silent-sync-failure class of bug from reaching main.

Reference:
[Infrahub schema docs](https://docs.infrahub.app)
