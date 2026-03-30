---
title: Peer Must Reference Full Kind
impact: CRITICAL
tags: relationship, peer, kind
---

## Peer Must Reference Full Kind

Impact: CRITICAL

The `peer` field on a relationship must use the full
kind (Namespace + Name), not just the name. Using just
the name causes a "peer not found" validation error.

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
