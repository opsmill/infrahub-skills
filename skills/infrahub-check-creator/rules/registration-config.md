---
title: Check Registration in .infrahub.yml
impact: HIGH
tags: registration, config, infrahub-yml, targets, parameters
---

## Check Registration in .infrahub.yml

Impact: HIGH

Checks must be registered in `.infrahub.yml` with
matching query names. Mismatched names cause silent
failures.

### Global Check Config

```yaml
queries:
  - name: rack_devices         # Query name
    file_path: queries/rack_devices.gql

check_definitions:
  - name: rack_unit_collision
    class_name: RackUnitCollision
    file_path: checks/rack_unit_collision.py
    # No targets = global check
```

### Targeted Check Config

```yaml
queries:
  - name: leaf_config
    file_path: queries/validation/leaf.gql

check_definitions:
  - name: leaf_validation
    class_name: LeafValidation
    file_path: checks/leaf.py
    targets: leaf_devices     # CoreCheckGroup name
    parameters:
      device: name__value     # Maps $device to name
```

### Critical Rules

- **`query` class attribute must match** the query
  `name` in `.infrahub.yml` exactly
- **Global checks** omit `targets` -- they run on every
  proposed change
- **Targeted checks** need both `targets` and
  `parameters`
- **`parameters`** maps GraphQL variable names to target
  object attributes

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
