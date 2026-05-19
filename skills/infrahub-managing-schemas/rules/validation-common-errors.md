---
title: Common Validation Errors and Fixes
impact: LOW
tags: validation, errors, debugging, additionalProperties
---

## Common Validation Errors and Fixes

Impact: LOW (but saves debugging time)

The Infrahub JSON schema uses
`additionalProperties: false`, meaning any typo in
property names causes a validation error. Here are the
most common errors and fixes.

### "Unknown field"

A typo in a property name:

```yaml
# BAD - typo
- name: MyNode
  namspace: Dcim         # Should be "namespace"
```

### "Name must match pattern"

Naming convention violation. See the
[naming-conventions](./naming-conventions.md) rule.

### "Peer not found"

Missing namespace in peer reference. See the
[relationship-peer-kind](./relationship-peer-kind.md) rule.

### "Identifier mismatch"

Bidirectional relationship identifiers don't match. See the
[relationship-identifiers](./relationship-identifiers.md) rule.

### "Relationship of type parent must not be optional"

A relationship with `kind: Parent` has `optional: true`
(or no explicit value — relationships default to
optional). Set `optional: false` on the Parent side.
See [relationship-component-parent](./relationship-component-parent.md).

### "Relationship of type parent must be cardinality=one"

A `kind: Parent` relationship has `cardinality: many`
or no explicit cardinality (which defaults to
`many`). Set `cardinality: one`. See
[relationship-component-parent](./relationship-component-parent.md).

### "Only one relationship of type parent is allowed"

A node has more than one relationship with
`kind: Parent`. Pick the canonical owner; model the
others as `kind: Attribute` or `kind: Generic`
references. See
[relationship-component-parent](./relationship-component-parent.md).

### "Uniqueness constraint references unknown field"

Wrong format in constraints. See the
[uniqueness-constraints](./uniqueness-constraints.md) rule.

### Pre-Validation Checklist

Before running `infrahubctl schema check`, verify:

- [ ] Every schema file starts with `version: "1.0"`
- [ ] All node/generic names are PascalCase
- [ ] All namespaces match `^[A-Z][a-z0-9]+$`
- [ ] All attribute/relationship names are snake_case, 3+ chars
- [ ] All `peer` values use full kind (namespace + name)
- [ ] All bidirectional relationships have matching `identifier`
- [ ] All Component relationships have a matching Parent
- [ ] Every `kind: Parent` relationship has
  `cardinality: one` and `optional: false`
- [ ] No node has more than one `kind: Parent`
  relationship
- [ ] All hierarchical nodes inherit from a `hierarchical: true` generic
- [ ] Root hierarchical nodes have `parent: null`
- [ ] All Dropdown attributes have `choices` defined
- [ ] `human_friendly_id` is set on user-facing nodes
- [ ] `uniqueness_constraints` use `__value` for attributes
- [ ] The `$schema` comment is present for IDE validation

```bash
# Validate
infrahubctl schema check schemas/

# Load
infrahubctl schema load schemas/ --branch main
```

Reference: [validation.md](../validation.md) for full validation and migration guide.
