---
name: infrahub-transform-creator
description: Create and manage Infrahub transforms. Use when building data transformations, config generation, or any workflow that converts Infrahub data into a different format (JSON, text, CSV, device configs) using Python or Jinja2 templates.
---

## Overview

Expert guidance for creating Infrahub transforms. Transforms convert Infrahub data into different formats -- JSON, text, CSV, device configs, or any text-based output -- using Python classes or Jinja2 templates.

## When to Use

- Building data transformations (Infrahub data -> another format)
- Generating device configurations from infrastructure data
- Creating CSV reports, cable matrices, or inventory exports
- Rendering Jinja2 templates with query data
- Combining Python logic with Jinja2 rendering
- Connecting transforms to artifacts for automated output

## Rule Categories

| Priority | Category | Prefix | Description |
|----------|----------|--------|-------------|
| CRITICAL | Transform Types | `types-` | Python vs Jinja2, when to use which |
| CRITICAL | Python Transform | `python-` | InfrahubTransform class, transform() method, return types |
| CRITICAL | Jinja2 Transform | `jinja2-` | Template syntax, data variable, netutils filters |
| HIGH | Hybrid | `hybrid-` | Python data prep + Jinja2 rendering pattern |
| HIGH | Artifacts | `artifacts-` | Connecting transforms to output files, content types, targets |
| HIGH | API Reference | `api-` | Class attributes, instance properties, methods |
| MEDIUM | Patterns | `patterns-` | Data extraction utilities, CSV output, shared common.py |
| LOW | Testing | `testing-` | infrahubctl transform/render commands |

## Transform Basics

Two types of transforms:

| Type | Output | Entry Point |
|------|--------|-------------|
| **Python** | JSON/dict or text | `InfrahubTransform.transform()` |
| **Jinja2** | Text | `.j2` template file |

```python
from infrahub_sdk.transforms import InfrahubTransform

class MyTransform(InfrahubTransform):
    query = "my_query"

    async def transform(self, data: dict) -> dict:
        device = data["DcimDevice"]["edges"][0]["node"]
        return {"hostname": device["name"]["value"]}
```

## Supporting References

- **[examples.md](./examples.md)** -- Complete transform patterns (Python, Jinja2, hybrid, CSV)
- **[../common/graphql-queries.md](../common/graphql-queries.md)** -- GraphQL query writing reference
- **[../common/infrahub-yml-reference.md](../common/infrahub-yml-reference.md)** -- .infrahub.yml project configuration
- **[../common/rules/](../common/rules/)** -- Shared rules (git integration, caching gotchas) that apply across all skills
- **[../schema-creator/SKILL.md](../schema-creator/SKILL.md)** -- Schema definitions transforms work with
- **[rules/](./rules/)** -- Individual rules organized by category prefix
