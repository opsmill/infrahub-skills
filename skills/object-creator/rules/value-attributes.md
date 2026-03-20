---
title: Attribute Value Mapping
impact: CRITICAL
tags: values, attributes, dropdown, text, number, boolean
---

## Attribute Value Mapping

Impact: CRITICAL

Schema attribute types map directly to YAML values. The
most common mistake is using a Dropdown `label` instead
of `name`.

### Type Mapping

| Schema Kind | YAML Value | Example |
| ----------- | ---------- | ------- |
| Text | string | `name: "My Device"` |
| Number | integer | `rack_u_position: 33` |
| Boolean | true/false | `is_full_depth: true` |
| Dropdown | choice name | `status: active` |
| DateTime | ISO string | `warranty_expire_date: "2027-01-01"` |

### Dropdown Values

**Incorrect -- using the label:**

```yaml
data:
  - name: my-device
    status: Active            # Wrong! "Active" is the label
    rack_face: Front          # Wrong! "Front" is the label
```

**Correct -- using the choice name:**

```yaml
data:
  - name: my-device
    status: active            # "active" is the choice name
    rack_face: front          # "front" is the choice name
```

The `name` value from `choices` in the schema is what you use, not the `label`.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
