---
title: Relationship Reference Mapping
impact: CRITICAL
tags: values, relationships, human_friendly_id, references
---

## Relationship Reference Mapping

Impact: CRITICAL

Reference related objects by their target node's
`human_friendly_id`. The shape — scalar or list —
follows the number of elements in that target's
`human_friendly_id`.

### Why it matters

The loader builds an HFID lookup mutation from the
value shape literally: a string becomes a
single-field match, a YAML list becomes a positional
multi-field match in the order declared on the
target schema. A scalar passed into a multi-element
HFID target lands on the wrong field, and the lookup
silently resolves to the wrong object or fails with
"node not found". List order also matters — swapping
two elements still produces a valid query but
matches a different (or no) row. That's why the
exact `human_friendly_id` order on the target schema
is the reference of truth for every example here.

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

Group membership is declared **on the member**, not
on the group. The group file (typically a
`CoreStandardGroup` or `CoreGeneratorGroup`) only
defines the group's identity; members opt in by
listing the group name(s) under their
`member_of_groups` relationship:

```yaml
# objects/groups.yml — the group itself
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreStandardGroup
  data:
    - name: leafs
      description: All leaf devices
    - name: cisco_leaf
      description: Cisco-vendor leaf devices

---
# objects/devices.yml — devices join groups from this side
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: "my-device"
      member_of_groups:
        - leafs
        - cisco_leaf
```

> **Setting members from the group side requires
> the `data:` wrapper.** A bare `members: - kind:
> DcimDevice / name: ...` under the group's spec is
> rejected by the object loader with `Invalid
> structure for a relationship of cardinality many,
> either provide a dict with data as a list or a
> list of objects`. The shape that does load is the
> same `data:`-wrapped pattern used for component
> children (`members: { data: [...] }`) — but
> setting membership from the **member side** via
> `member_of_groups: [...]` is the simpler
> ergonomic and the convention every artifact and
> generator pipeline in this repo follows.
> `targets:` in `.infrahub.yml` references a group
> name, and the group's members come from each
> device's `member_of_groups` list, not from inline
> members declared on the group object.

**Key rule**: the value shape mirrors the target
node's `human_friendly_id` — scalar for a
single-element HFID, list (in declared order) for a
multi-element HFID.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
