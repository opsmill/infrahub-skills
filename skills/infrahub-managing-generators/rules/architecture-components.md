---
title: Generator Architecture and Components
impact: CRITICAL
tags: architecture, components, target-group, triggers
---

## Generator Architecture and Components

Impact: CRITICAL

Generators consist of three components that work
together for design-driven automation: a target
group, a GraphQL query, and a Python class.

### Why it matters

The dispatcher links these three by name: the target
group's members trigger the run, the named query
fetches the design payload, and the Python class
processes it. If the target group is a
`CoreStandardGroup` instead of `CoreGeneratorGroup`,
the dispatcher never sees it and the generator
silently never fires — the proposed change appears
to "do nothing". The query and class are decoupled
on purpose so the same design data can feed multiple
generators, but each piece has to be present and
named correctly for the chain to resolve.

### Three Components

1. **Target group** -- a `CoreGeneratorGroup` containing
   objects that trigger generation
2. **GraphQL query** (`.gql` file) -- fetches the
   design/template data
3. **Python class** -- inherits from `InfrahubGenerator`,
   implements `generate()`

### Execution Triggers

Generators run automatically when:

- Target objects change in proposed changes
  (`execute_in_proposed_change=True`, default)
- After branch merges
  (`execute_after_merge=True`, default)

### Example Query

```graphql
query topology($name: String!) {
  TopologyDataCenter(name__value: $name) {
    edges {
      node {
        id
        name { value }
        design {
          node {
            elements {
              edges {
                node {
                  ... on DesignElement {
                    quantity { value }
                    role { value }
                    device_type { node { id } }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### File Organization

```text
generators/
  __init__.py              # Optional: package init
  common.py                # Shared utilities
  generate_dc.py           # DC topology generator
  generate_pop.py          # POP topology generator

queries/
  topology/
    dc.gql                 # Query for DC topology data
    pop.gql                # Query for POP topology data
```

Reference: [examples.md](../examples.md) for complete
generator examples.
