---
title: Extensions for Cross-File Relationships
impact: MEDIUM
tags: extension, cross-file, modular
---

## Extensions for Cross-File Relationships

Impact: MEDIUM

When schema file A defines `OrganizationTenant` and
schema file B defines `LocationRack`, use the
`extensions` block to add a relationship from Rack to
Tenant without modifying file A.

**Incorrect -- modifying the original schema file to add a cross-dependency:**

If you add the relationship directly to
`organization.yml`, that file now depends on
`location.yml` existing, creating a circular
dependency risk.

**Correct -- using extensions block:**

```yaml
# In a separate file (e.g., extensions/location.yml):
extensions:
  nodes:
    - kind: LocationRack           # Target node (must already exist)
      relationships:
        - name: tenant
          peer: OrganizationTenant
          kind: Attribute
          cardinality: one
          optional: true
          identifier: "tenant__racks"
```

**Alternative -- add directly on the node that owns the relationship:**

```yaml
# In location.yml where Rack is defined:
nodes:
  - name: Rack
    namespace: Location
    relationships:
      - name: tenant
        peer: OrganizationTenant
        kind: Attribute
        cardinality: one
        optional: true
        identifier: "tenant__racks"
```

**When to use extensions:**

- Adding relationships to nodes you don't own (e.g., BuiltinTag, CoreRepository)
- Keeping schema files focused on their domain
- Avoiding circular dependencies between schema files

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
