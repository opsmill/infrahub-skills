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
  version: 1.2.4
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
5. **Register in .infrahub.yml** — Add under
   `generator_definitions` with the target group. See
   [rules/registration-config.md](./rules/registration-config.md).
6. **Test** — Run `infrahubctl generator` to validate.
   See [rules/testing-commands.md](./rules/testing-commands.md).

## Supporting References

- **[examples.md](./examples.md)** -- Complete Generator
  patterns (POP topology, network segment, minimal)
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching gotchas)
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**
  -- Schema definitions Generators work with
- **[rules/](./rules/)** -- Individual rules organized by
  category prefix
