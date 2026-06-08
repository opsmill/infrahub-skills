---
title: Order Weight Conventions
impact: MEDIUM
tags: display, order_weight, ui
---

## Order Weight Conventions

Impact: MEDIUM

`order_weight` controls UI display order for
attributes and relationships — lower values appear
first.

### Why it matters

Without `order_weight`, the UI falls back to YAML
declaration order, which drifts every time someone
reorganizes the file and produces a different
attribute layout on each schema edit. Picking values
from a shared range (key relationships in 800–900,
core attributes in 1000–1999, etc.) keeps the same
field in the same slot across nodes, which matters
when users move between similar object views. Leaving
gaps between values is what makes future inserts
cheap — without them, adding a new "primary" field
requires renumbering everything around it.

**Recommended convention:**

| Range | Use For |
| ----- | ------- |
| 800-900 | Key relationships (rack, device_type) |
| 1000-1999 | Core attributes (name, model, status) |
| 2000-2999 | Secondary attributes (description, serial, weight) |
| 3000+ | Tags and metadata relationships |

**Example:**

```yaml
attributes:
  - name: name
    kind: Text
    order_weight: 1000
  - name: status
    kind: Dropdown
    order_weight: 1500
  - name: description
    kind: Text
    optional: true
    order_weight: 2000
relationships:
  - name: rack
    peer: LocationRack
    order_weight: 900            # Key relationship appears before attributes
  - name: tags
    peer: BuiltinTag
    order_weight: 3000           # Tags at the bottom
```

**Tip:** Leave gaps between values (1000, 1100, 1200) so
you can insert new fields without renumbering everything.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
