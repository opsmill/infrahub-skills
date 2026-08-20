---
title: Uniqueness Constraint Format
impact: MEDIUM
tags: uniqueness, constraints, validation, mandatory, cardinality
---

## Uniqueness Constraint Format

Impact: MEDIUM

Uniqueness constraints reference attributes with the
`__value` suffix and relationships by bare name. A
relationship used in a constraint must also be
mandatory and single-valued.

### Why it matters

The two field types are stored differently inside
Infrahub — attributes have a `__value` accessor for
the scalar value behind the property wrapper, while
relationships resolve to peer objects directly. The
constraint validator does an exact field-name lookup,
so `name` (without `__value`) and `rack__value` (with
the suffix on a relationship) both fail schema load
with `uniqueness constraint references unknown
field`. The error message names the wrong field but
not the right one, which is why the rule lives here:
it's the format you have to know in advance.

**Incorrect:**

```yaml
uniqueness_constraints:
  - ["name", "rack"]             # Missing __value on attribute
  - ["name__value", "rack__value"]  # __value on relationship
```

**Correct:**

```yaml
uniqueness_constraints:
  - ["name__value", "rack"]      # __value for attributes, bare name for relationships
```

### Format Rules

| Field Type | Format | Example |
| ---------- | ------ | ------- |
| Attribute | `attribute_name__value` | `name__value` |
| Relationship | bare name | `rack`, `device_type`, `manufacturer` |

### Relationship Preconditions

Naming a relationship in a constraint is not enough —
the relationship itself has to be shaped so the
constraint can be evaluated. All three conditions
below are checked at schema load.

| Requirement | On the relationship | Error if violated |
| ----------- | ------------------- | ----------------- |
| Mandatory | `optional: false` | `cannot use <name> relationship, relationship must be mandatory` |
| Single-valued | `cardinality: one` | `cannot use <name> relationship, relationship must be of cardinality one` |
| Bare name only | no peer-attribute path | `cannot use attributes of related node, only the relationship` |

The mandatory requirement is the one that surprises
people: a constraint scoped by a relationship can only
be enforced if every object actually has that
relationship set. If the relationship were optional,
objects with no peer would have nothing to be unique
*within*, so Infrahub rejects the schema rather than
silently skipping those objects.

This bites hardest on `kind: Attribute` relationships,
which are optional unless you say otherwise. A
`kind: Parent` relationship is already required to be
`optional: false` and `cardinality: one`, so it
satisfies the preconditions for free. See
[relationship-defaults](./relationship-defaults.md)
for the default values.

**Incorrect** — `cluster` is optional, so the schema
does not load:

```yaml
uniqueness_constraints:
  - ["cluster", "vmid__value"]
relationships:
  - name: cluster
    peer: VirtualizationCluster
    kind: Attribute
    cardinality: one
    optional: true
```

**Correct:**

```yaml
uniqueness_constraints:
  - ["cluster", "vmid__value"]
relationships:
  - name: cluster
    peer: VirtualizationCluster
    kind: Attribute
    cardinality: one
    optional: false
```

If making the relationship mandatory is wrong for your
data model — the peer genuinely may be unset — then
scoped uniqueness is the wrong tool. Drop the
constraint and enforce the rule in a check instead.

### Example: Unique Device Name per Rack

```yaml
nodes:
  - name: PDU
    namespace: Dcim
    uniqueness_constraints:
      - ["rack", "name__value"]   # Name is unique within each rack
    human_friendly_id:
      - name__value
      - rack__name__value
    attributes:
      - name: name
        kind: Text
    relationships:
      - name: rack
        peer: DcimRack
        kind: Attribute
        cardinality: one
        optional: false           # Required — see Relationship Preconditions
        identifier: rack__pdu
```

### The Same Rule Reaches human_friendly_id

A `human_friendly_id` is also converted into a
uniqueness constraint behind the scenes, so a
relationship used in an HFID must meet the same
preconditions. The confusing part is the error: it is
reported against `uniqueness_constraints` even when
you never wrote one.

```yaml
# No uniqueness_constraints on this node at all, yet
# schema load fails with:
#   DcimPdu.uniqueness_constraints: cannot use rack
#   relationship, relationship must be mandatory. (`rack`)
human_friendly_id:
  - name__value
  - rack__name__value
relationships:
  - name: rack
    peer: DcimRack
    kind: Attribute
    cardinality: one
    optional: true              # <-- the actual cause
```

If a `uniqueness_constraints` error names a
relationship you never put in a constraint, look at
the node's `human_friendly_id`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
