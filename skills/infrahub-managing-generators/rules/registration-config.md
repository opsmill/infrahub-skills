---
title: Generator Registration in .infrahub.yml
impact: HIGH
tags: registration, config, infrahub-yml, targets, parameters
---

## Generator Registration in .infrahub.yml

Impact: HIGH

A generator is registered in `.infrahub.yml` under
`generator_definitions` with its query name, target
group, class name, and the parameter mapping that
turns target attributes into query variables.

### Why it matters

`generator_definitions` carries a top-level `query:`
field — the opposite of `check_definitions`, which
embeds the query under the check itself. Copying the
check shape into a generator block is the most
common setup mistake; Infrahub rejects the config at
load time and the generator never appears in
`infrahubctl generator --list`. `targets:` resolves
strictly against `CoreGeneratorGroup`; pointing it
at a `CoreStandardGroup` of the same name parses
fine but the dispatcher never enqueues runs, so the
generator looks broken with no error message.
Parameter paths like `name__value` are evaluated on
each member of the target group at dispatch time —
a typo here surfaces as the query running with
empty variables and returning zero rows.

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

- `query` is matched by exact string against the
  `queries` block; a mismatch (or a missing
  `queries` entry) makes the dispatcher report an
  unknown query and skip the run.
- `targets` resolves only against
  `CoreGeneratorGroup`; pointing it at a different
  group kind parses but never triggers, so the
  generator looks dead with no log line.
- `parameters` maps GraphQL `$variable` names to
  target attribute paths (`name__value`,
  `site__node__name__value`); the path is evaluated
  per group member at dispatch time.

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
