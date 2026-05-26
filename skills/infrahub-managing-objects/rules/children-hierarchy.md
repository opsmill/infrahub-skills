---
title: Hierarchical Children Nesting
impact: HIGH
tags: children, hierarchy, locations, nesting
---

## Hierarchical Children Nesting

Impact: HIGH

Hierarchical children (location trees and similar)
nest inline under `children`, with a `kind` field at
each level.

### Why it matters

A hierarchical generic like `LocationGeneric` covers
many concrete kinds (`LocationSite`, `LocationRoom`,
`LocationRack`), so the loader can't infer which
schema applies from the parent alone. Without `kind`
on the child wrapper, the loader doesn't know which
node type to instantiate and the branch is rejected
— even if every other field is valid. Inline nesting
also drives Infrahub's auto-resolution of the
`parent`/`children` relationship, which is what
makes the tree appear in the UI without explicit
parent references on each row.

**Incorrect -- missing kind on children:**

```yaml
data:
  - name: "AMERICAS"
    children:
      data:
        - name: "Boston HQ"          # What kind is this? Ambiguous!
```

**Correct -- kind specified at each level:**

```yaml
data:
  - name: "AMERICAS"
    shortname: "amer"
    children:
      kind: LocationSite              # Concrete child kind
      data:
        - name: "Boston HQ"
          shortname: "bos"
          children:
            kind: LocationRoom
            data:
              - name: "Lab-1"
                shortname: "lab-1"
                children:
                  kind: LocationRack
                  data:
                    - name: "Rack-A"
                      height: 42
```

### Rules

- `children` carries a `kind` field and a `data` array
- `kind` names the schema node type for that level
- Nesting depth is unlimited — it mirrors the schema
  hierarchy
- Parent references auto-resolve from the nesting

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
