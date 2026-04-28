---
title: Component/Parent Pairs Must Match
impact: CRITICAL
tags: relationship, component, parent, identifier, optional, cardinality
---

## Component/Parent Pairs Must Match

Impact: CRITICAL

Component and Parent relationships are paired. The
Component side (parent owns children) must be
`cardinality: many`, the Parent side (child points to
parent) must be `cardinality: one`. Both must share
the same `identifier`. The Parent side is also
constrained: a node can have **at most one** parent
relationship, and it must **not** be optional.

**Incorrect:**

```yaml
# TenantGroup has tenants (Component side)
- name: tenants
  peer: OrganizationTenant
  kind: Component
  cardinality: one               # WRONG - Component should be many

# Tenant belongs to group (Parent side)
- name: group
  peer: OrganizationTenantGroup
  kind: Parent
  cardinality: many              # WRONG - Parent should be one
  # optional defaults to true   # WRONG - Parent must not be optional
```

**Correct:**

```yaml
# TenantGroup has tenants (Component side)
- name: tenants
  peer: OrganizationTenant
  kind: Component
  cardinality: many              # Component = many children
  identifier: "group__tenants"

# Tenant belongs to group (Parent side)
- name: group
  peer: OrganizationTenantGroup
  kind: Parent
  cardinality: one               # Parent = one parent
  optional: false                # Parent must be required
  identifier: "group__tenants"   # Same identifier
```

**Rule summary:**

- Component side: `kind: Component`, `cardinality: many`
- Parent side: `kind: Parent`, `cardinality: one`,
  `optional: false`
- At most **one** `kind: Parent` relationship per node
- Both sides: same `identifier`

### Parent-Side Constraints (enforced server-side)

`infrahubctl schema check` and the server both run
`_validate_parents_one_schema`, which raises on:

| Violation | Error message |
| --------- | ------------- |
| Two or more `kind: Parent` rels on a node | `Only one relationship of type parent is allowed, but all the following are of type parent: [...]` |
| Parent rel with `cardinality: many` | `Relationship of type parent must be cardinality=one` |
| Parent rel with `optional: true` (or unset — relationships default to optional) | `Relationship of type parent must not be optional` |

Why required: a node whose `kind` is structurally a
child (Component on the parent side) is meaningless
without its owner. Allowing the parent link to be
unset would let orphaned children exist, which would
also break cascade-delete semantics on the Component
side. Marking it `optional: false` is what enforces
"every child has a parent" at validation time.

**Common gotcha:** relationships default to
`optional: true` (unlike attributes, which default to
mandatory). For `kind: Parent` you must explicitly
set `optional: false` — leaving it unset triggers the
error above.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
