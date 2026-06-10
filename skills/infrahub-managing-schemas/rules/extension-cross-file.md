---
title: Extensions for Cross-File Relationships
impact: MEDIUM
tags: extension, cross-file, modular
---

## Extensions for Cross-File Relationships

Impact: MEDIUM

Add cross-domain relationships via the `extensions`
block rather than editing the foreign node's source
file.

### Why it matters

A schema file that references a kind defined in
another file inherits that file's load order as a
dependency. Editing `organization.yml` to point at
`LocationRack` couples the two files in both
directions: `organization.yml` now fails to load
without `location.yml`, and `location.yml` cannot
move into another project without dragging
organization with it. Extensions invert the
dependency — the consuming file owns the link — so
each domain file stays loadable on its own and
removable without rewriting another team's schema.

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
    - kind: LocationRack           # Target node — defined elsewhere
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

**What `extensions:` cannot do**

The `extensions:` block only accepts new
`attributes:` and `relationships:` on an existing
**node** (no `generics:` subkey). Adding
`inherit_from`, `display_label`, `human_friendly_id`,
`uniqueness_constraints`, `hierarchical`, or any
other top-level property either raises
`ValidationError` (server-side schema parse) or is
silently dropped (SDK-side parse), depending on
the code path. In both cases the extension has no
effect.

To change anything other than attributes or
relationships on a kind you don't own, edit that
kind's source schema file. If the kind lives in a
shared bundle you don't control, define your own
concrete node that inherits from the foreign
generic plus whatever base you need (e.g.,
`CoreArtifactTarget`), and target your node
instead.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
