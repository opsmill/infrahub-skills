---
title: Relationship Reference Mapping
impact: CRITICAL
tags: values, relationships, human_friendly_id, references
---

## Relationship Reference Mapping

Impact: CRITICAL

Reference related objects by their `human_friendly_id`.
The format depends on whether the target's
`human_friendly_id` has one or multiple elements.

### Single-Element human_friendly_id (scalar)

When the target has `human_friendly_id: [name__value]`:

```yaml
data:
  - name: "PowerEdge R660xs"
    manufacturer: Dell                # Scalar -- matches by name
```

### Multi-Element human_friendly_id (list)

When the target has `human_friendly_id: [parent__shortname__value, name__value]`:

```yaml
data:
  - name: "My Server"
    rack: ["lab-1", "Rack-A"]         # List -- matches [room_shortname, rack_name]
```

### Platform References

```yaml
data:
  - name: "my-switch"
    platform: [Juniper, JunOS]        # [manufacturer_name, platform_name]
```

### Module Bay References

When the target has `human_friendly_id: [device_type__model__value, name__value]`:

```yaml
data:
  - device: TEST-R660xs-1
    bay:
      - PowerEdge R660xs              # device_type model
      - PSU1                          # bay name
```

### Group Membership (cardinality: many)

```yaml
data:
  - name: "my-device"
    member_of_groups:
      - leafs
      - cisco_leaf
```

**Key rule**: The value you provide must match the target
node's `human_friendly_id`. Scalar for single-element,
list for multi-element.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
