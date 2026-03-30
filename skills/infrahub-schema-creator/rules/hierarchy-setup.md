---
title: Setting Up Hierarchical Nodes
impact: HIGH
tags: hierarchy, parent, children, generic, location
---

## Setting Up Hierarchical Nodes

Impact: HIGH

Hierarchical nodes (like location trees) require three
things: a generic with `hierarchical: true`, nodes with
`parent`/`children` fields, and inheritance from that
generic.

### Step 1: Generic with hierarchical: true

```yaml
generics:
  - name: Generic
    namespace: Location
    hierarchical: true            # Enables the parent/children hierarchy
    attributes:
      - name: name
        kind: Text
        unique: true
      - name: shortname
        kind: Text
```

### Step 2: Nodes with parent and children

```yaml
nodes:
  - name: Region
    namespace: Location
    inherit_from: [LocationGeneric]
    parent: null                   # Root of hierarchy (no parent)
    children: LocationSite         # Expected child kind

  - name: Site
    namespace: Location
    inherit_from: [LocationGeneric]
    parent: LocationRegion         # Expected parent kind
    children: LocationRoom         # Expected child kind

  - name: Room
    namespace: Location
    inherit_from: [LocationGeneric]
    parent: LocationSite
    children: LocationRack

  - name: Rack
    namespace: Location
    inherit_from: [LocationGeneric]
    parent: LocationRoom
    children: null                 # Leaf of hierarchy (no children)
```

**Incorrect -- missing any of the three requirements:**

```yaml
# Missing hierarchical: true on generic
generics:
  - name: Generic
    namespace: Location
    # hierarchical: true  <-- MISSING

# Missing inherit_from
nodes:
  - name: Region
    namespace: Location
    parent: null                   # Will fail without hierarchical generic
```

**Key rules:**

- Root nodes: `parent: null`
- Leaf nodes: `children: null` (or omit)
- Use full kind for `parent` and `children` values: `LocationSite` not `Site`

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
