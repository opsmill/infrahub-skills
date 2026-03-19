---
name: infrahub-generator-creator
description: Create and manage Infrahub generators. Use when building design-driven automation that creates infrastructure objects from templates, topology definitions, or any design-to-implementation workflow in Infrahub.
metadata:
  version: 1.1.0
  author: OpsMill
---

## Overview

Expert guidance for creating Infrahub generators. Generators query data from Infrahub via GraphQL and create new nodes and relationships based on the result -- enabling design-driven automation where a "design" object automatically creates downstream infrastructure.

## When to Use

- Building design-driven automation (topology -> devices)
- Creating objects from templates or design definitions
- Implementing idempotent create-or-update workflows
- Auto-generating infrastructure from high-level designs
- Understanding the generator tracking system

## Rule Categories

| Priority | Category | Prefix | Description |
|----------|----------|--------|-------------|
| CRITICAL | Architecture | `architecture-` | Three components, target groups, execution triggers |
| CRITICAL | Python Class | `python-` | InfrahubGenerator, async generate(), object creation API |
| HIGH | Tracking | `tracking-` | delete_unused_nodes, allow_upsert, idempotent behavior |
| HIGH | API Reference | `api-` | Constructor params, instance properties, methods |
| HIGH | Registration | `registration-` | .infrahub.yml config, parameters mapping |
| MEDIUM | Patterns | `patterns-` | Data cleaning, batch creation, local store |
| LOW | Testing | `testing-` | infrahubctl generator commands |

## Generator Basics

Every generator has three components:

1. **Target group** -- objects that trigger the generator
2. **GraphQL query** (`.gql` file) -- fetches the design data
3. **Python class** -- inherits from `InfrahubGenerator`, implements `generate()`

```python
from infrahub_sdk.generator import InfrahubGenerator

class MyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        obj = await self.client.create(kind="DcimDevice", data={"name": "spine-01"})
        await obj.save(allow_upsert=True)  # Idempotent: create or update
```

## Supporting References

- **[examples.md](./examples.md)** -- Complete generator patterns (POP topology, network segment, minimal)
- **[../common/graphql-queries.md](../common/graphql-queries.md)** -- GraphQL query writing reference
- **[../common/infrahub-yml-reference.md](../common/infrahub-yml-reference.md)** -- .infrahub.yml project configuration
- **[../common/rules/](../common/rules/)** -- Shared rules (git integration, caching gotchas) that apply across all skills
- **[../schema-creator/SKILL.md](../schema-creator/SKILL.md)** -- Schema definitions generators work with
- **[rules/](./rules/)** -- Individual rules organized by category prefix
