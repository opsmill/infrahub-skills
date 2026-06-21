---
title: Decompose Denormalized CSVs Into Numbered Kinds
impact: HIGH
description: >-
  When a single CSV conflates multiple kinds (e.g. device + location +
  manufacturer in one sheet, or device rows repeated per interface),
  detect the denormalization, propose a split in the interview, and emit
  the split as NN-prefixed files so the loader sees referents before
  referrers.
tags: decomposition, denormalized, split, components, load-order
---

## Decompose Denormalized CSVs Into Numbered Kinds

Impact: HIGH

When a single CSV conflates multiple kinds (e.g.,
device + location + manufacturer in one sheet, or
device rows repeated per interface), detect the
denormalization, propose a split in the interview,
and emit the split as numbered files so the loader
sees referents before referrers.

### Why it matters

Loaded literally, a denormalized CSV causes:

1. **Wrong cardinality.** Repeated parent rows
   with per-child columns collapse to a single
   child value unless the emission recognizes
   the repetition.
2. **Load-order failures.** A device referencing
   a manufacturer by HFID needs the manufacturer
   to exist first. Both kinds in one file means
   the loader sees the reference before the
   referent and the whole batch aborts.

The right split depends on the user's intent —
sometimes children belong inline (interfaces of a
device), sometimes as a separate kind referenced by
multiple parents (sites referenced by devices and
racks). The interview makes the call; this rule
covers detection and emission patterns.

### Detection signals

A CSV is denormalized when one or more of these
holds:

| Signal | Interpretation |
| ------ | -------------- |
| Some columns are constant per group of rows (group key shifts every N rows) | Those columns belong to a parent kind; the rest belong to the child |
| Multiple groups of columns share an obvious prefix (e.g., `manufacturer_name`, `manufacturer_country`) | The prefix-group is a separate kind referenced from the main one |
| The same row's "primary key" repeats with different values in other columns | Either repeated parent (component children) or a many-to-many that needs splitting |

The denormalization detector is heuristic — the
interview confirms.

### Two emission patterns, both valid

#### Pattern A: inline component children

The child has no meaning outside the parent
(interfaces of a device, slots of a rack).
Component/Parent relationships make this load
atomically. See
[../../infrahub-managing-objects/rules/children-components.md](../../infrahub-managing-objects/rules/children-components.md).

```yaml
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      interfaces:
        kind: InterfacePhysical
        data:
          - name: Ethernet1
            role: uplink
          - name: Ethernet2
            role: uplink
```

When to pick this:
- Children are referenced by no other kind.
- Their lifecycle is bound to the parent (delete
  parent ⇒ delete children).
- The schema declares the Component side with a
  matching Parent identifier on the child side.

#### Pattern B: split into separate numbered kinds

The child is independently queryable, referenced
by multiple parents, or has a decoupled lifecycle.
See
[../../infrahub-managing-objects/rules/organization-load-order.md](../../infrahub-managing-objects/rules/organization-load-order.md).

```text
output_dir/
  01_manufacturers.yml      # standalone, referenced by 03 and 04
  02_sites.yml              # standalone, referenced by 04
  03_device_types.yml       # references 01
  04_devices.yml            # references 02 and 03
```

When to pick this:
- The child kind shows up as a reference target
  elsewhere in the load (or in existing data).
- The schema declares Attribute-kind relationships
  rather than Component/Parent.
- The user wants the children to be addressable
  on their own.

### The interview surfaces the choice

```text
Your CSV repeats device columns (name, role) for
each interface, suggesting one of two shapes:

a) Inline interfaces as Component children of
   DcimDevice (single 03_devices.yml, interfaces
   nest inline). Pick this if interfaces are
   bound to their device lifecycle.

b) Split into 03_devices.yml + 04_interfaces.yml
   with HFID references. Pick this if interfaces
   are also referenced elsewhere (cabling, link
   state, telemetry).

The schema declares interfaces as Component
children of DcimDevice — both shapes load, but
(a) matches the schema's intent.
```

### Numbering matters

The numeric prefixes in the emitted filenames are
what gives `infrahubctl object load` a
deterministic load order across the directory. A
device file that references a manufacturer must
have a higher prefix than the manufacturer file —
otherwise the loader hits an HFID lookup failure
and aborts the whole batch (no second-pass retry).

### Common mistakes

- **Emitting the denormalized sheet as one file
  per kind without numeric prefixes.** Load order
  becomes filesystem-dependent and the loader's
  HFID lookups race the inserts.
- **Picking inline component children when the
  schema declares an Attribute-kind
  relationship.** The component wrapper (`kind:
  ... data: [...]`) is the wrong shape for a
  non-Component relationship and the loader will
  reject it.
- **Auto-picking the split without asking.** The
  user knows their domain; the split is their
  call. Always confirm in the interview.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
