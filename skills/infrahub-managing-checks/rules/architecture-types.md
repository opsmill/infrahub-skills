---
title: Check Architecture and Types
impact: CRITICAL
tags: architecture, global, targeted, components
---

## Check Architecture and Types

Impact: CRITICAL

Every check consists of three components — a GraphQL
query, a Python class, and a `.infrahub.yml`
registration — and a choice between *global* (runs
every change) and *targeted* (runs when group members
change) execution.

### Why it matters

The three pieces are bound by name, not by file
layout: the Python class's `query` attribute names a
`queries[]` entry, and `check_definitions[]` points
at the class. Get any of the three out of sync and
Infrahub either rejects the repo config at load time
or runs the check against an empty payload, with no
hint to the user about which leg of the triangle is
broken. The global-vs-targeted choice also dictates
query shape — a targeted check needs GraphQL
variables bound from `parameters:`, while a global
check fetches the full set in one go.

### Three Components

1. **GraphQL query** (`.gql` file) -- fetches the data
   to validate
2. **Python class** -- inherits from `InfrahubCheck`,
   implements `validate()`
3. **Configuration** -- declared in `.infrahub.yml`
   under `check_definitions`

### Two Types of Checks

<!-- markdownlint-disable MD013 -->

| Type | `targets` field | Runs when | Use case |
| ---- | --------------- | --------- | -------- |
| **Global** | Omitted | Every proposed change | Validate all objects of a type |
| **Targeted** | Group name | Target objects change | Validate specific objects in a group |

<!-- markdownlint-enable MD013 -->

### Global Check Query (no variables)

```graphql
query RackDevices {
  DcimGenericDevice {
    edges {
      node {
        id
        __typename
        display_label
        name { value }
        rack { node { id name { value } } }
      }
    }
  }
}
```

### Targeted Check Query (with variable)

```graphql
query leaf_config($device: String!) {
  DcimDevice(name__value: $device) {
    edges {
      node {
        id
        name { value }
        interfaces {
          edges {
            node {
              name { value }
              role { value }
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
checks/
  __init__.py              # Optional: package
  common.py                # Optional: shared utils
  rack_unit_collision.py   # Check modules
  leaf.py

queries/
  rack_devices.gql         # Global queries
  validation/
    leaf_validation.gql    # Targeted queries
```

Reference: [examples.md](../examples.md) for complete
check examples.
