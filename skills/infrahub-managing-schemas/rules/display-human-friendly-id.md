---
title: Always Set human_friendly_id on Nodes
impact: HIGH
tags: display, human_friendly_id, identity
---

## Always Set human_friendly_id on Nodes

Impact: HIGH

`human_friendly_id` determines how objects are identified
in the UI and how they're referenced from object data
files. Without it, objects can only be referenced by
internal UUID.

**Incorrect -- no human_friendly_id:**

```yaml
nodes:
  - name: DeviceType
    namespace: Dcim
    # No human_friendly_id -- objects can't be easily referenced
```

**Correct:**

```yaml
nodes:
  - name: DeviceType
    namespace: Dcim
    human_friendly_id:
      - model__value               # Single element = scalar reference
```

### Path Syntax

- Local attributes: `attribute_name__value`
- Traverse relationships: `relationship__attribute__value`
- Multi-level: `parent__shortname__value`

### Single vs Multi-Element

| Elements | Reference Style | Example |
| -------- | --------------- | ------- |
| 1 element | Scalar | `device_type: PowerEdge R960` |
| 2+ elements | List | `rack: ["room-short", "Rack-A"]` |

### Examples

```yaml
# Simple -- referenced as: manufacturer: Dell
human_friendly_id:
  - name__value

# Composite -- referenced as: rack: ["01-4", "TEST-RACK1"]
human_friendly_id:
  - parent__shortname__value
  - name__value

# Through relationship -- referenced as: bay: ["PowerEdge R960", "PSU1"]
human_friendly_id:
  - device_type__model__value
  - name__value
```

Also set `display_label` for UI rendering (supports Jinja2):

```yaml
display_label: "{{ manufacturer__name__value }} {{ name__value }}"
```

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
