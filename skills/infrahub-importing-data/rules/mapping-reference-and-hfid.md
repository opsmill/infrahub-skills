---
title: Detect Reference Columns and Match the HFID Shape
impact: CRITICAL
description: >-
  Detect reference columns by name + value-shape match against the target
  kind's human_friendly_id, then emit a scalar for single-element HFIDs and
  a YAML list in declared order for multi-element HFIDs. Never invent the
  HFID order.
tags: mapping, references, hfid, scalar, list
---

## Detect Reference Columns and Match the HFID Shape

Impact: CRITICAL

Detect CSV columns that represent relationships
(not attributes) by matching the column name
against the target node's relationship list **and**
verifying the value shape lines up with the target
kind's `human_friendly_id`. Emit the reference
shape — scalar for a single-element HFID, list for
multi-element — exactly as the target schema
declares.

The full HFID emission rules live in
[../../infrahub-managing-objects/rules/value-relationships.md](../../infrahub-managing-objects/rules/value-relationships.md);
this rule adds the detection step that comes
before emission.

### Why it matters

A column that looks like a foreign key (e.g.,
`site_name`, `manufacturer`) needs to be emitted
as a relationship reference, not an attribute.
Two shapes have to be correct simultaneously:

1. **The detection is right.** A column called
   `address` could be either an attribute or a
   reference to an `Address` node — only the
   schema decides.
2. **The reference shape matches the HFID.** The
   loader builds an HFID lookup mutation from the
   YAML value literally: a scalar becomes a
   single-field match, a list becomes a positional
   multi-field match in declared order. Get the
   shape wrong and the lookup either fails ("node
   not found") or silently resolves to the wrong
   row.

### Detection: name + value shape

A column is a reference candidate when:

- Its name matches a relationship on the target
  kind (exact match, or snake_case round-trip,
  using the same ladder as
  [mapping-column-to-attribute.md](./mapping-column-to-attribute.md)).
- **And** its values look like the target kind's
  HFID — string for a single-element HFID, or a
  tuple/joined form for a multi-element HFID.

If the name matches a relationship but the values
don't fit the HFID shape (e.g., the column carries
UUIDs while the target has `hfid: [name__value]`),
surface it in the interview — the user may have
exported IDs instead of names.

### Scalar reference (single-element HFID)

When the target's HFID is `[name__value]`:

```yaml
data:
  - name: spine-01
    manufacturer: Arista        # scalar — matches the single-element HFID
    site: par-1
```

### List reference (multi-element HFID)

When the target's HFID is `[parent__shortname__value,
name__value]`:

```yaml
data:
  - name: rack-01
    room: ["lab-1", "Room-A"]   # list, in declared order
```

The list order matters. Swapping the two elements
produces a valid query that matches a different
row, or no row at all. Always read the order from
the schema; never re-order to "make it look right."

### Reading HFID order from the schema

The target's `human_friendly_id` is a list at the
node level:

```yaml
nodes:
  - name: Rack
    namespace: Dcim
    human_friendly_id:
      - room__shortname__value
      - name__value
```

The reference list is `[<room-shortname>, <rack-name>]`,
in that order. The schema is the reference of truth —
not the CSV column order, not the user's intuition.

### Cardinality:many references

Some relationships are cardinality:many (e.g.,
`member_of_groups` on a device). The CSV
representation is typically one column with a
comma-separated value (or a join across multiple
columns). Detection works the same way; emission
is a YAML list:

```yaml
data:
  - name: spine-01
    member_of_groups:
      - leafs
      - production
```

Group membership is declared on the member side,
not on the group side — see
[../../infrahub-managing-objects/rules/value-relationships.md](../../infrahub-managing-objects/rules/value-relationships.md).

### Common mistakes

- **Treating every "foreign-key-ish" column as an
  attribute.** A `manufacturer` column on a
  `devices.csv` is almost certainly a reference,
  not a Text attribute. Check the schema's
  relationship list before binding to an
  attribute.
- **Inventing HFID order.** Always read the order
  from the target node's schema. The CSV doesn't
  carry that information.
- **Padding a single-element list to look like a
  multi-element one.** A target with
  `hfid: [name__value]` takes a scalar. Wrapping
  it as `[Arista]` parses but binds to the wrong
  field if the target ever gains a second HFID
  element.
- **Missing the cardinality:many split.** A
  comma-separated CSV cell needs to become a YAML
  list, not a single comma-containing string.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
