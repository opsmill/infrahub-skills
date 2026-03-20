---
title: Component/Parent Pairs Must Match
impact: CRITICAL
tags: relationship, component, parent, identifier
---

## Component/Parent Pairs Must Match

Impact: CRITICAL

Component and Parent relationships are paired. The
Component side (parent owns children) must be
`cardinality: many`, the Parent side (child points to
parent) must be `cardinality: one`. Both must share
the same `identifier`.

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
  identifier: "group__tenants"   # Same identifier
```

**Rule summary:**

- Component side: `kind: Component`, `cardinality: many`
- Parent side: `kind: Parent`, `cardinality: one`
- Both: same `identifier`

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
