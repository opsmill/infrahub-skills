---
title: Uniqueness Constraint Format
impact: MEDIUM
tags: uniqueness, constraints, validation
---

## Uniqueness Constraint Format

Impact: MEDIUM

Uniqueness constraints use `__value` suffix for
attributes but bare names for relationships. Getting
this wrong causes a "references unknown field"
validation error.

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
      - ["rack", "name__value"]   # Name must be unique within each rack
    human_friendly_id:
      - name__value
      - rack__name__value
```

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
