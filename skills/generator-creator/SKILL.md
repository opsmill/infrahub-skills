---
name: infrahub-generator-creator
description: >-
  Create and manage Infrahub Generators. Use when building
  design-driven automation that creates infrastructure objects
  from templates, topology definitions, or any
  design-to-implementation workflow in Infrahub.
metadata:
  version: 1.1.0
  author: OpsMill
---

# Infrahub Generator Creator

## Overview

Expert guidance for creating Infrahub Generators. Generators
query data from Infrahub via GraphQL and create new nodes and
relationships based on the result -- enabling design-driven
automation where a "design" object automatically creates
downstream infrastructure.

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

## MCP Server Integration

When the Infrahub MCP server is connected, use it to
understand existing data before building generators:

- **Inspect design objects** — call
  `mcp__infrahub__infrahub_query` to see what
  design-level objects exist and their data shape
- **Discover schema kinds** — call
  `mcp__infrahub__infrahub_list_schema` to confirm the
  kinds a generator will create
- **Verify target groups** — query existing groups to
  confirm generator target membership before writing
  configuration

See [../common/mcp-tools-reference.md](../common/mcp-tools-reference.md)
for tool definitions and usage patterns.

## Supporting References

- **[examples.md](./examples.md)** -- Complete Generator
  patterns (POP topology, network segment, minimal)
- **[../common/mcp-tools-reference.md](../common/mcp-tools-reference.md)**
  -- MCP tool reference for live instance queries
- **[../common/graphql-queries.md](../common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[../common/infrahub-yml-reference.md](../common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../common/rules/](../common/rules/)** -- Shared rules
  (git integration, caching gotchas)
- **[../schema-creator/SKILL.md](../schema-creator/SKILL.md)**
  -- Schema definitions Generators work with
- **[rules/](./rules/)** -- Individual rules organized by
  category prefix
