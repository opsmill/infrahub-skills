---
title: Self-Check Emission Against Managing-Objects Rules
impact: CRITICAL
description: >-
  After emitting object YAML and before creating any branch, walk every
  file against the managing-objects rules (envelope, value shape, HFID
  arity, component wrappers, range syntax, load order). Local only; fix
  in place before the next step.
tags: workflow, self-check, managing-objects, validation, local-first
---

## Self-Check Emission Against Managing-Objects Rules

Impact: CRITICAL

After emitting object YAML and before creating any
branch, re-read the listed rules from
`infrahub-managing-objects` and walk every emitted
file against each one. Local only — no CLI, no
server, no branch yet. Fix in place before the next
step.

### Why it matters

Server validate only catches schema-resolution
errors (kind missing, attribute typo, reference
target not found). Shape errors that the consumer
skill explicitly forbids — dropdown labels instead
of choice names, wrong HFID arity, component
children emitted as bare lists — slip past validate
and only surface as wrong data after load. The
self-check catches them locally, before any branch
exists.

### Which rules to re-read

| Rule | What to verify |
| ---- | -------------- |
| [../../infrahub-managing-objects/rules/format-structure.md](../../infrahub-managing-objects/rules/format-structure.md) | Every doc has `apiVersion: infrahub.app/v1`, `kind: Object`, `spec.kind`, `spec.data` as a list |
| [../../infrahub-managing-objects/rules/value-attributes.md](../../infrahub-managing-objects/rules/value-attributes.md) | Dropdown values use the choice `name`, not the `label`; Number values are integers, not strings |
| [../../infrahub-managing-objects/rules/value-relationships.md](../../infrahub-managing-objects/rules/value-relationships.md) | Single-element HFID targets get scalar refs; multi-element get YAML lists in declared order |
| [../../infrahub-managing-objects/rules/children-components.md](../../infrahub-managing-objects/rules/children-components.md) | Component children wrap in `kind:` + `data:` when the relationship peer is a generic |
| [../../infrahub-managing-objects/rules/range-expansion.md](../../infrahub-managing-objects/rules/range-expansion.md) | Range syntax sits in `data:` items; `expand_range: true` lives on `parameters:`, not on individual items |
| [../../infrahub-managing-objects/rules/organization-load-order.md](../../infrahub-managing-objects/rules/organization-load-order.md) | Files use numeric prefixes; dependent kinds load after their referents |

### How to run the self-check

For each emitted file:

1. Parse the YAML.
2. Walk every key against the rule table above.
3. On failure, fix in place and re-walk from step
   1 (the fix may introduce its own violations).
4. Only when every file walks cleanly, proceed to
   [workflow-branch-before-load.md](./workflow-branch-before-load.md).

### Common mistakes

- **Skipping the self-check because validate will
  catch it.** Validate runs on a branch that has
  to be created first — and validate only catches
  what the server can see, not the shape errors
  this check exists to prevent.
- **Re-implementing the managing-objects rules
  inline.** Always read the source rules. If they
  change, the import skill picks up the change
  automatically; if you inline them, the contract
  drifts silently.
- **Treating the self-check as advisory.** It
  isn't — it's the local correctness gate. A
  failed self-check means the emission gets fixed,
  not noted and shipped.

### Rationalizations — and why they don't hold

| Rationalization | Reality |
| --------------- | ------- |
| "Validate will catch shape errors." | Validate needs a branch first and only sees schema-resolution errors. Dropdown-label-vs-name and wrong HFID arity pass validate and corrupt data after load. |
| "I emitted it carefully; re-walking is redundant." | The self-check is the only local correctness gate. Careful emission still drifts on component wrappers and `expand_range` placement. |
| "I'll self-check after creating the branch." | Then a shape-error emission leaves an orphan branch. The self-check is local-only, before any branch exists. |

### Red flags — stop and re-walk

- About to run `branch create` without having walked every file against the managing-objects rules.
- "The emission looks right" without re-reading the source rules.
- Treating a self-check failure as a note to ship rather than a fix to make.

Any of these means: stop, re-read the managing-objects rules, and walk every file before the branch step.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
