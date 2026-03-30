---
title: Hierarchical Children Nesting
impact: HIGH
tags: children, hierarchy, locations, nesting
---

## Hierarchical Children Nesting

Impact: HIGH

For hierarchical nodes (location trees), nest children
inline with the `kind` field specified on each level.

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
      kind: LocationSite              # Must specify child kind
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

- `children` must contain a `kind` field and a `data` array
- `kind` specifies the schema node type of the child objects
- Nesting depth is unlimited -- matches your schema hierarchy
- The hierarchy auto-resolves parent references

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
