---
title: Attribute Defaults, Dropdowns, and Deprecated Fields
impact: HIGH
tags: attribute, optional, dropdown, choices, deprecated
---

## Attribute Defaults, Dropdowns, and Deprecated Fields

Impact: HIGH

### Attributes Are Mandatory by Default

Unlike relationships (which default to optional),
attributes default to `optional: false`. If you add a
new attribute without `optional: true`, all existing
objects will need a value.

**Incorrect -- adding a new required attribute without a default:**

```yaml
- name: serial_number
  kind: Text
  # optional defaults to false -- existing objects will fail validation!
```

**Correct -- add as optional first, or provide a default:**

```yaml
- name: serial_number
  kind: Text
  optional: true              # Safe for existing data

# OR
- name: serial_number
  kind: Text
  default_value: "unknown"    # Provides fallback for existing data
```

### Dropdown Choices Format

Each choice needs at minimum a `name` field. `label`,
`description`, `color` are optional.

**Incorrect:**

```yaml
- name: status
  kind: Dropdown
  choices:
    - active                  # Must be an object with name field, not a bare string
    - planned
```

**Correct:**

```yaml
- name: status
  kind: Dropdown
  choices:
    - name: active
      label: Active
      color: "#00FF00"
    - name: planned
      label: Planned
      color: "#0000FF"
```

When referencing dropdown values in object files, use
the `name` value (not `label`): `status: active` not
`status: Active`.

### Deprecated Fields to Avoid

| Deprecated | Use Instead |
| ---------- | ----------- |
| `display_labels` | `display_label` |
| `default_filter` | `human_friendly_id` |
| `String` (attribute kind) | `Text` |
| `regex` (top-level) | `parameters: { regex: "..." }` |
| `min_length` (top-level) | `parameters: { min_length: N }` |
| `max_length` (top-level) | `parameters: { max_length: N }` |

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
