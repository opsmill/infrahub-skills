---
title: Common Object Patterns
impact: LOW
tags: patterns, flat-list, parent-child, devices, git-repo
---

## Common Object Patterns

Impact: LOW (reference patterns)

Worked examples of the shapes the loader expects for
the recurring cases: flat lists, devices with full
reference fan-out, empty rack slots, and git repo
objects.

### Why it matters

The other rules describe the envelope and the value
mapping; this file shows them composed. Copying from
a working pattern is the fastest way to avoid the
common mistakes — list-vs-scalar HFID confusion,
forgetting `status: empty` on vacant slots, mixing
device and component fields at the wrong level —
because the patterns embed the rule choices instead
of asking the reader to recombine them from scratch.

### Flat List (No Relationships)

```yaml
spec:
  kind: OrganizationManufacturer
  data:
    - name: Dell
    - name: Intel
    - name: Juniper
```

### Device with All References

```yaml
spec:
  kind: DcimDellServer
  data:
    - name: prod-server-01
      device_type: PowerEdge R960
      rack: ["lab-1", "Rack-A"]
      rack_u_position: 1
      rack_face: front
      status: active
      serial: "ABC123"
      asset_tag: "DELL-001"
      warranty_expire_date: "2027-01-01"
      tenant: Engineering
```

### Empty/Vacant Slots

```yaml
spec:
  kind: DcimModuleInstallation
  data:
    - device: prod-server-01
      slot_name: PCIe Slot 3
      bay:
        - PowerEdge R960
        - PCIe Slot 3
      status: empty              # No module_type = vacant slot
```

### Git Repository Object

```yaml
spec:
  kind: CoreRepository
  data:
    - name: my-repo
      location: "/upstream"
      default_branch: "main"
```

See [examples.md](../examples.md) for 15 complete patterns.
