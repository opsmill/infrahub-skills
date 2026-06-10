---
title: Setting Up Hierarchical Nodes
impact: HIGH
tags: hierarchy, parent, children, generic, location
---

## Setting Up Hierarchical Nodes

Impact: HIGH

Hierarchical nodes require all three pieces wired
together: a generic with `hierarchical: true`,
concrete nodes that `inherit_from` that generic, and
explicit `parent`/`children` kind references on each
level.

### Why it matters

`parent` and `children` are only resolved when the
inheriting node sits under a `hierarchical: true`
generic — without the generic, the fields parse but
the hierarchy machinery stays dormant, so the
location tree UI shows a flat list and `parent`
queries return nothing. The kind references use the
full `Namespace + Name` form for the same reason
`peer` does: short names cause "node not found" at
load. Roots are marked with `parent: null` and
leaves with `children: null` (or omitted) so the
loader knows where the chain terminates rather than
searching for a missing parent kind.

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
