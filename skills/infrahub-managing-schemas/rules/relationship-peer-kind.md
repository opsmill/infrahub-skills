---
title: Peer References the Full Kind
impact: CRITICAL
tags: relationship, peer, kind
---

## Peer References the Full Kind

Impact: CRITICAL

The `peer` field on a relationship uses the full
kind (Namespace + Name), not the bare name.

### Why it matters

Infrahub resolves peers by full kind because the bare
name is ambiguous across namespaces — `Device` could
mean `DcimDevice`, `VirtualDevice`, or `MobileDevice`
depending on which file is loaded. The resolver
treats a short reference as a kind that does not
exist and the schema load fails with "peer not
found"; the same lookup powers `inherit_from`,
`parent`, `children`, and `menu_placement`, so the
rule is the same wherever a kind is referenced.

**Incorrect:**

```yaml
relationships:
  - name: device_type
    peer: DeviceType              # Missing namespace!
    kind: Attribute
    cardinality: one
```

**Correct:**

```yaml
relationships:
  - name: device_type
    peer: DcimDeviceType          # Full kind: Dcim + DeviceType
    kind: Attribute
    cardinality: one
```

This applies everywhere a kind is referenced: `peer`,
`inherit_from`, `parent`, `children`, `menu_placement`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
