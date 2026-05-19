---
title: Relationship Default Values
impact: CRITICAL
tags: relationship, defaults, cardinality, optional
---

## Relationship Default Values

Impact: CRITICAL

Relationship defaults are different from attribute
defaults. Getting these wrong leads to unexpected
behavior.

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
wrong here, so you must set it explicitly. Leaving it
unset (or `true`) fails schema check with
`Relationship of type parent must not be optional`.
See
[relationship-component-parent.md](./relationship-component-parent.md).

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
