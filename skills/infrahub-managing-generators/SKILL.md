---
name: infrahub-managing-generators
description: >-
  Creates Infrahub Generators — design-driven automation that builds infrastructure objects from templates and topology definitions.
  TRIGGER when: building design-to-implementation workflows, auto-creating objects from templates, topology-driven generation.
  DO NOT TRIGGER when: designing schemas, writing data transforms, querying live data, populating static data files.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
argument-hint: "[generator-name] [description...]"
metadata:
  version: 1.2.7
  author: OpsMill
---

# Infrahub Generator Creator

## Overview

Expert guidance for creating Infrahub Generators. Generators
query data from Infrahub via GraphQL and create new nodes and
relationships based on the result -- enabling design-driven
automation where a "design" object automatically creates
downstream infrastructure.

## Project Context

Infrahub config:
!`cat .infrahub.yml 2>/dev/null || echo "No .infrahub.yml found"`

Existing generators:
!`find . -name "*.py" -path "*/generators/*" 2>/dev/null | head -20`

## When to Use

- Building design-driven automation (topology -> devices)
- Creating objects from templates or design definitions
- Implementing idempotent create-or-update workflows
- Auto-generating infrastructure from high-level designs
- Understanding the generator tracking system

## Rule Categories

| Priority | Category     | Prefix          | Description            |
| -------- | ------------ | --------------- | ---------------------- |
| CRITICAL | Architecture | `architecture-` | Components, groups     |
| CRITICAL | Python Class | `python-`       | Generator, generate()  |
| HIGH     | Tracking     | `tracking-`     | Upsert, idempotent     |
| HIGH     | API Ref      | `api-`          | Constructor, props     |
| HIGH     | Registration | `registration-` | .infrahub.yml config   |
| MEDIUM   | Patterns     | `patterns-`     | Cleaning, batch, store |
| LOW      | Testing      | `testing-`      | infrahubctl commands   |

## Schema Features This Skill Depends On

Generators create real objects, so the schema must
permit the shape they emit. Catch these gaps before
the first run — re-running a buggy generator can
delete data via the tracking cleanup.

| If the generator... | The schema must... | See |
| ------------------- | ------------------ | --- |
| Creates objects of kind X | Have node X defined with the attributes the generator sets — extra attributes silently fail validation, missing required ones abort the create | [../infrahub-managing-schemas/rules/attribute-defaults-and-types.md](../infrahub-managing-schemas/rules/attribute-defaults-and-types.md) |
| Links the created object to a parent | Have a Component/Parent relationship pair with matching identifiers and `optional: false` on the Parent side | [../infrahub-managing-schemas/rules/relationship-component-parent.md](../infrahub-managing-schemas/rules/relationship-component-parent.md) |
| Reads a "design" node to drive output | Define that node's `human_friendly_id` so the generator's tracking key stays stable across runs | [../infrahub-managing-schemas/rules/display-human-friendly-id.md](../infrahub-managing-schemas/rules/display-human-friendly-id.md) |
| Is triggered by membership in a group | The target group must be a `CoreGeneratorGroup` (not `CoreStandardGroup`) — the dispatcher only recognizes the former | [rules/registration-config.md](./rules/registration-config.md) |
| Should be idempotent on re-run | Every `save()` uses `allow_upsert=True`; the run's tracking context deletes objects from prior runs that aren't recreated | [rules/tracking-idempotent.md](./rules/tracking-idempotent.md) |

## Before writing Python

A generator should *compute* objects from a design. If
what you're about to write is "make these N specific
objects from a hardcoded list," that list is data —
move it to `objects/` and either let the object
loader handle it directly or pass it into a smaller
generator. Walk this ladder before reaching for
`InfrahubGenerator`:

| Signal | Cheaper layer | See rule |
| ------ | ------------- | -------- |
| Generator hardcodes object lists, role catalogs, or status sets | YAML data files under `objects/` (loaded by the object loader) | [yagni-generator-hardcoding-data](../infrahub-auditing-repo/rules/yagni-generator-hardcoding-data.md) |
| Generator recreates a built-in IPAM/VLAN primitive (custom IP address, prefix, VLAN nodes) | `inherit_from: [BuiltinIPAddress / BuiltinIPPrefix / IpamVLAN]` in the schema, then the generator computes references rather than reimplementing the primitive | [yagni-custom-domain-primitives-instead-of-builtin](../infrahub-auditing-repo/rules/yagni-custom-domain-primitives-instead-of-builtin.md) |
| Generator's output shape duplicates objects already in `opsmill/schema-library` | `inherit_from` a library generic; the generator computes the *instance* but not the *shape* | [yagni-duplicate-shape-not-extracted-to-generic](../infrahub-auditing-repo/rules/yagni-duplicate-shape-not-extracted-to-generic.md) |
| Generator allocates a subnet/IP/VLAN/port with `ipaddress` math, `random`, or a hand-written "find the first free one" loop | A built-in resource pool — `allocate_next_ip_prefix` / `allocate_next_ip_address`, `CoreIPPrefixPool` / `CoreNumberPool` — which tracks utilization and stays idempotent across re-runs | [yagni-imperative-allocation-vs-resource-pool](../infrahub-auditing-repo/rules/yagni-imperative-allocation-vs-resource-pool.md) |
| `generate()` stamps a fixed set of children with constant values and no computation (no branching, derived naming, or allocation) | An Object Template (`generate_template: true`) users clone — the structure lives in data, not Python | [yagni-generator-that-should-be-template](../infrahub-auditing-repo/rules/yagni-generator-that-should-be-template.md) |

Bootstrap, seed, and demo generators (under
`bootstrap/`, `seed/`, `demo/`) are exempt — they
exist specifically to hardcode initial state. Use
Python when the generator is genuinely computing
objects from a design definition; see
[rules/python-generate.md](./rules/python-generate.md)
for the legitimate cases.

## Generator Basics

Every generator has three components:

1. **Target group** -- objects that trigger the generator
2. **GraphQL query** (`.gql` file) -- fetches the design data
3. **Python class** -- inherits from `InfrahubGenerator`,
   implements `generate()`

```python
from infrahub_sdk.generator import InfrahubGenerator

class MyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        obj = await self.client.create(
            kind="DcimDevice",
            data={"name": "spine-01"},
        )
        await obj.save(allow_upsert=True)
```

## Workflow

Follow these steps when creating a generator:

1. **Identify the design pattern** — What "design"
   object triggers generation? What objects should be
   created from it? Read
   [rules/architecture-components.md](./rules/architecture-components.md)
   for the target group and generator components.
2. **Write the GraphQL query** — Create a `.gql` file
   that fetches the design data. Read
   [../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)
   for query patterns.
3. **Implement the Python class** — Inherit from
   `InfrahubGenerator`, implement `generate()`. Read
   [rules/python-generate.md](./rules/python-generate.md)
   for the class pattern and
   [rules/api-reference.md](./rules/api-reference.md)
   for available methods.
4. **Make it idempotent** — Use `allow_upsert=True` so
   re-running creates or updates without duplicates.
   See [rules/tracking-idempotent.md](./rules/tracking-idempotent.md).
5. **Check for `from_graphql` adoption opportunity** — if
   `generate()` iterates response edges and calls
   `self.client.get()` to re-fetch typed peers, consider
   refactoring to `InfrahubNode.from_graphql()` to collapse
   `O(N + 1)` round trips to `O(1)`. Read
   [rules/patterns-hydration.md](./rules/patterns-hydration.md)
   for the decision tree, detection heuristic, and refactor
   recipe.
6. **Register in .infrahub.yml** — Add under
   `generator_definitions` with the target group. See
   [rules/registration-config.md](./rules/registration-config.md).
7. **Test** — Run `infrahubctl generator` to validate.
   See [rules/testing-commands.md](./rules/testing-commands.md).

## Supporting References

- **[reference.md](./reference.md)** -- Class API,
  lifecycle, idempotency contract, `.infrahub.yml`
  registration (with the `query:`-required shape that
  differs from check_definitions)
- **[examples.md](./examples.md)** -- Complete Generator
  patterns (POP topology, network segment, minimal)
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching gotchas)
- **[../infrahub-common/rules/workflow-information-priority.md](../infrahub-common/rules/workflow-information-priority.md)**
  -- Skill content first; how to consult `docs.infrahub.app`
  on a genuine gap (e.g. deleting nodes)
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**
  -- Schema definitions Generators work with
- **[rules/](./rules/)** -- Individual rules organized by
  category prefix
