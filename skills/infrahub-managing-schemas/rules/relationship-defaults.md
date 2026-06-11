---
title: Relationship Default Values
impact: CRITICAL
tags: relationship, defaults, cardinality, optional
---

## Relationship Default Values

Impact: CRITICAL

Relationship defaults diverge from attribute
defaults: `cardinality` defaults to `many`, and
`optional` defaults to `true`.

### Why it matters

The cardinality default is the trap — a relationship
written without `cardinality:` is read as
`many`, even when the field name is singular
(`rack`, `device_type`, `manufacturer`). Infrahub
then expects a list everywhere the relationship is
written or queried, the UI renders a multi-select
where users expected a single picker, and object
files that pass a single value fail validation.
Equally, `optional: true` being the default lets a
`kind: Parent` slip through with no parent required —
the server then rejects schema load with
`Relationship of type parent must not be optional`,
but only after the mismatched intent has shaped
surrounding code.

| Property | Default | Notes |
| -------- | ------- | ----- |
| `cardinality` | `many` | Explicitly set `one` for singles |
| `optional` | `true` | Unlike attrs (mandatory default) |
| `direction` | `bidirectional` | Rarely needs changing |
| `kind` | `Generic` | Set for Component, Parent, Attr |

**Common mistake -- forgetting cardinality defaults to many:**

```yaml
# Incorrect: Missing cardinality, defaults to many
- name: rack
  peer: LocationRack
  kind: Attribute
  # cardinality defaults to "many" -- probably not what you want for a rack reference!
```

```yaml
# Correct: Explicitly set cardinality: one
- name: rack
  peer: LocationRack
  kind: Attribute
  cardinality: one
```

**Key contrast with attributes:** Attributes are
`optional: false` by default (mandatory). Relationships
are `optional: true` by default.

| Type | Default `optional` |
| ---- | ------------------ |
| Attributes | `false` (mandatory) |
| Relationships | `true` (optional) |

**Exception — `kind: Parent` rejects `optional: true`:**
The server validates that any relationship with
`kind: Parent` has `optional: false`. The default is
wrong here, so set it explicitly. Leaving it unset
(or `true`) fails schema check with
`Relationship of type parent must not be optional`.
See
[relationship-component-parent.md](./relationship-component-parent.md).

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
