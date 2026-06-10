---
title: Uniqueness Constraint Format
impact: MEDIUM
tags: uniqueness, constraints, validation
---

## Uniqueness Constraint Format

Impact: MEDIUM

Uniqueness constraints reference attributes with the
`__value` suffix and relationships by bare name.

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
```

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
