---
title: Check Registration in .infrahub.yml
impact: HIGH
tags: registration, config, infrahub-yml, targets, parameters, no-query-field
---

## Check Registration in .infrahub.yml

Impact: HIGH

Register checks under `check_definitions` in
`.infrahub.yml`; the query is **not** declared here —
it is bound from the Python class's `query` attribute,
which must match a `name` under the top-level
`queries:` section.

### Why it matters

`InfrahubCheckDefinitionConfig` is a Pydantic model
configured with `extra="forbid"`, so adding a
`query:` key under a check entry — the single most
common mistake, borrowed from
`generator_definitions` which *does* take one —
raises `extra fields not permitted` and fails the
whole repository config. The repo then refuses to
load and *every* check in the file is unavailable,
not just the broken one. The corollary failure is
silent: if the class's `query = "..."` string does
not match a `queries[].name`, the SDK fetches nothing,
`validate(data)` runs against an empty payload, and
the check passes vacuously — letting bad data merge
unnoticed.

### Allowed Fields (and only these)

`InfrahubCheckDefinitionConfig` is a Pydantic model
with `extra="forbid"`. Any unknown key — including
`query` — causes the repository config to fail
validation and the check fails to load.

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier for the check definition |
| `file_path` | Yes | Path to the Python file containing the check class |
| `class_name` | No | Python class name (defaults to `Check` if omitted) |
| `targets` | No | `CoreGroup` name for targeted checks; omit for global |
| `parameters` | No | Maps GraphQL variable names → target attribute paths |

### `query` Does NOT Belong Here

The single most common mistake is copying the
`generator_definitions` shape (which *does* take a
top-level `query:`) into `check_definitions`.

**Wrong** — fails with a Pydantic
`extra fields not permitted` error:

```yaml
check_definitions:
  - name: leaf_validation
    file_path: checks/leaf.py
    query: leaf_config      # ❌ NOT a valid field
    targets: leafs
```

**Right** — the query lives on the Python class, and
the name there matches an entry in `queries:`:

```yaml
queries:
  - name: leaf_config              # ← class.query points here
    file_path: queries/leaf.gql

check_definitions:
  - name: leaf_validation
    class_name: LeafValidation
    file_path: checks/leaf.py      # contains: query = "leaf_config"
    targets: leafs
    parameters:
      device: name__value
```

```python
class LeafValidation(InfrahubCheck):
    query = "leaf_config"          # ← matches queries[].name
```

The data flow: `class.query` → `queries[].name` →
`queries[].file_path`. Skipping the `queries:` section
or putting the query path directly on the check both
fail.

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
    targets: leaf_devices     # CoreGroup name
    parameters:
      device: name__value     # Maps $device to name
```

### Critical Rules

- **`query` class attribute must match** the query
  `name` in `.infrahub.yml` exactly. Mismatched names
  cause silent failures (no data is fetched).
- **Do not add `query:` under `check_definitions`** —
  it is rejected by `extra="forbid"`. This differs
  from `generator_definitions`, which requires it.
- **Global checks** omit `targets` — they run on every
  proposed change.
- **Targeted checks** need both `targets` and
  `parameters` (when the query has variables).
- **`parameters`** maps GraphQL variable names to
  target object attribute paths (e.g.,
  `name__value`).

### Why This Differs From Generators

Generators run **once per group member** and need the
query injected with that member's attributes — the
runtime needs to know the query at registration time
to bind variables, so `query:` is a top-level field.

Checks are *associated* with their query via the class
itself; the class is the single source of truth for
which query backs which check. Splitting that across
two files is what `extra="forbid"` is preventing.

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
