---
title: Relationship Default Values
impact: CRITICAL
tags: relationship, defaults, cardinality, optional
---

## Relationship Default Values

Impact: CRITICAL

Relationship defaults differ from attribute defaults
in cardinality and kind. Getting these wrong leads to
unexpected behavior.

| Property | Default | Notes |
| -------- | ------- | ----- |
| `cardinality` | `many` | Explicitly set `one` for singles |
| `optional` | `false` | Same as attrs (mandatory default) |
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

**Same default as attributes:** Both attributes and
relationships default to `optional: false` (mandatory).

| Type | Default `optional` |
| ---- | ------------------ |
| Attributes | `false` (mandatory) |
| Relationships | `false` (mandatory) |

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
