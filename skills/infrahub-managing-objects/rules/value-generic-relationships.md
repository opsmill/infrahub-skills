---
title: Generic Relationship References
impact: CRITICAL
tags: values, relationships, generics, human_friendly_id, LocationGeneric
---

## Generic Relationship References

Impact: CRITICAL

When a relationship targets a generic type (e.g.,
`LocationGeneric`) that does not have a
`human_friendly_id` defined, the standard scalar or
list HFID reference syntax will fail with:

> Unable to lookup node by HFID, schema
> 'LocationGeneric' does not have a HFID defined.

Use the inline data block with an explicit `kind:` to
specify the concrete type instead.

### Problem: Direct Reference to Generic

```yaml
# FAILS — LocationGeneric has no HFID
data:
  - prefix: "10.0.0.0/24"
    location: "Acacias"
```

### Solution: Inline Data with Concrete Kind

```yaml
# WORKS — specifies concrete type with HFID
data:
  - prefix: "10.0.0.0/24"
    location:
      kind: LocationSite
      data:
        - name: "Acacias"
```

### Why This Works

`infrahubctl object load` uses upsert behavior
(`allow_upsert=True`) for all objects, including
inline relationship data. When the loader processes
the inline block:

1. It resolves `kind: LocationSite` to the concrete
   schema (which has an HFID)
2. Creates an in-memory node with the provided data
3. Sends a `LocationSiteUpsert` GraphQL mutation
4. Infrahub matches the existing object by HFID and
   returns it (no duplicate created)
5. Uses that node's ID to establish the relationship

### When to Use This Pattern

- Relationship `peer` is a generic (e.g.,
  `LocationGeneric`, `GenericInterfaceL3`)
- The generic does not define `human_friendly_id`
- The concrete type you want to reference **does**
  have `human_friendly_id`
- The target object already exists (or should be
  created if missing)

### Multiple Concrete Types

Different objects can reference different concrete
types through the same generic relationship:

```yaml
data:
  # This prefix is at a site
  - prefix: "10.0.0.0/24"
    location:
      kind: LocationSite
      data:
        - name: "Acacias"
  # This prefix is at a building
  - prefix: "10.1.0.0/24"
    location:
      kind: LocationBuilding
      data:
        - name: "Building H"
```

**Key rule**: Always specify `kind:` when the
relationship targets a generic type. Use only the
fields needed to match the concrete type's
`human_friendly_id`.
