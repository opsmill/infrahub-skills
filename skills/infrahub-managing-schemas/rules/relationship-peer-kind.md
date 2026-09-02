---
title: Peer References the Full Kind
impact: CRITICAL
tags: relationship, peer, kind, generics, inheritance
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

## An Inherited Relationship's Peer Cannot Be Narrowed

A relationship inherited from a generic keeps that
generic's `peer`. A kind that inherits it cannot narrow
or widen the peer, and the attempt is caught at
`infrahubctl schema check`, before any data is touched.

### Why it matters

This is the constraint that bites the shape this skill
recommends. The "extract a generic when siblings repeat
a relationship" advice produces two flat generics
peering each other, with several concrete kinds on each
side. The next thing an author wants is to say "this
specific kind of port only attaches to this specific
kind of device", and that is precisely what is refused.

The consequence is a real modelling limit, not a detail:
**a schema built from flat generics cannot express which
concrete kinds pair with which.** The pairing has to
live in a Python check, or go unenforced. Knowing that
up front changes the design; learning it afterwards
means a type hierarchy was built around a rule the
server will not accept.

### It fails symmetrically

Narrowing from the child side, where the concrete kind
redeclares the inherited relationship with a concrete
peer:

```text
DcimOpticalPort's relationship device inherited from DcimPort
must have the same peer (DcimDevice != DcimSwitch)
```

Narrowing from the other side, redeclaring the reverse
relationship on the concrete kind there, fails the same
way:

```text
DcimSwitch's relationship ports inherited from DcimDevice
must have the same peer (DcimPort != DcimOpticalPort)
```

There is no side to attack it from.

### Two exemptions

The peer check is skipped for:

- **Hierarchy relationships** (`kind: Hierarchy`, and the
  `parent` / `children` fields a `hierarchical: true`
  generic generates). This is why a location hierarchy
  can have `GeoRegion` declare `children: GeoSite` while
  `GeoSite` declares `parent: GeoRegion`, both inheriting
  the same generic. Hierarchies are the one place
  kind-to-kind pairing *is* expressible.
- **The object-template relationship.**

So "an inherited peer can never change" is wrong as a
flat statement. If your pairing is genuinely a
containment hierarchy, model it as one and the
constraint does not apply. See
[hierarchy-setup.md](hierarchy-setup.md).

### A different error for a different cause

If the generic's relationship carries
`allow_override: none`, redeclaring it at all fails
earlier and for another reason:

```text
DcimOpticalPort's relationship device inherited from DcimPort cannot be overriden
```

That one is about permission to override, not about the
peer. Read which message you got before changing
anything.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
