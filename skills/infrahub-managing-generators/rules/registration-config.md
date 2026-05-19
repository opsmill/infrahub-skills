---
title: Generator Registration in .infrahub.yml
impact: HIGH
tags: registration, config, infrahub-yml, targets, parameters
---

## Generator Registration in .infrahub.yml

Impact: HIGH

Generators must be registered in `.infrahub.yml` with
query name, target group, and parameter mapping.

### Configuration

```yaml
queries:
  - name: topology_dc
    file_path: queries/topology/dc.gql

generator_definitions:
  - name: create_dc
    file_path: generators/generate_dc.py
    # Must match query name
    query: topology_dc
    # CoreGeneratorGroup name
    targets: topologies_dc
    class_name: DCTopologyGenerator
    parameters:
      # Maps $name to target's name attribute
      name: name__value
```

### Field Reference

| Field        | Required | Description                           |
| ------------ | -------- | ------------------------------------- |
| `name`       | Yes      | Unique Generator identifier           |
| `file_path`  | Yes      | Path to Python file                   |
| `query`      | Yes      | Query name (must match queries entry) |
| `targets`    | Yes      | CoreGeneratorGroup name               |
| `class_name` | Yes      | Python class name                     |
| `parameters` | Yes      | Maps query variables to attributes    |

### Critical Rules

- `query` must match the query `name` in the `queries`
  section
- `targets` references a `CoreGeneratorGroup` -- create
  the group first
- `parameters` maps GraphQL `$variable` names to target
  object attribute paths (e.g., `name__value`)

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
