---
title: Attribute Value Mapping
impact: CRITICAL
tags: values, attributes, dropdown, text, number, boolean
---

## Attribute Value Mapping

Impact: CRITICAL

Schema attribute kinds map onto specific YAML value
shapes. Dropdown attributes take the choice `name`,
not the display `label`.

### Why it matters

Dropdown choices are stored by their machine `name`
(typically lowercase, like `active`) and rendered in
the UI with the human `label` (`Active`). The loader
validates submitted values against the `name` list,
so passing the label produces a hard rejection:
`'Active' is not a valid choice for status`. Type
mismatches on other kinds (string into a Number
attribute, untyped date into DateTime) fail the same
way at upsert time, so the type table below isn't
cosmetic — each mapping is what survives validation.

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
