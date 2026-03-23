---
title: Order Weight Conventions
impact: MEDIUM
tags: display, order_weight, ui
---

## Order Weight Conventions

Impact: MEDIUM

`order_weight` controls the display order of attributes
and relationships in the Infrahub UI. Lower values
appear first. Use consistent ranges across your schema.

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
