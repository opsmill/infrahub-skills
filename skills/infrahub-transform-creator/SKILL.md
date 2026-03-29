---
name: infrahub-transform-creator
description: >-
  Create and manage Infrahub transforms. Use when building
  data transformations, config generation, or any workflow
  that converts Infrahub data into a different format
  (JSON, text, CSV, device configs) using Python or Jinja2
  templates.
metadata:
  version: 1.1.0
  author: OpsMill
---

# Infrahub Transform Creator

## Overview

Expert guidance for creating Infrahub transforms.
Transforms convert Infrahub data into different formats
-- JSON, text, CSV, device configs, or any text-based
output -- using Python classes or Jinja2 templates.

## When to Use

- Building data transformations (Infrahub data -> another format)
- Generating device configurations from infrastructure data
- Creating CSV reports, cable matrices, or inventory exports
- Rendering Jinja2 templates with query data
- Combining Python logic with Jinja2 rendering
- Connecting transforms to artifacts for automated output

## Rule Categories

| Priority | Category  | Prefix       | Description               |
| -------- | --------- | ------------ | ------------------------- |
| CRITICAL | Types     | `types-`     | Python vs Jinja2 choice   |
| CRITICAL | Python    | `python-`    | InfrahubTransform class   |
| CRITICAL | Jinja2    | `jinja2-`    | Template syntax, filters  |
| HIGH     | Hybrid    | `hybrid-`    | Python + Jinja2 combined  |
| HIGH     | Artifacts | `artifacts-` | Output files, targets     |
| HIGH     | API Ref   | `api-`       | Class attrs, methods      |
| MEDIUM   | Patterns  | `patterns-`  | Utilities, CSV, shared    |
| LOW      | Testing   | `testing-`   | Transform/render commands |

## Transform Basics

Two types of transforms:

| Type       | Output            | Entry Point                     |
| ---------- | ----------------- | ------------------------------- |
| **Python** | JSON/dict or text | `InfrahubTransform.transform()` |
| **Jinja2** | Text              | `.j2` template file             |

```python
from infrahub_sdk.transforms import InfrahubTransform

class MyTransform(InfrahubTransform):
    query = "my_query"

    async def transform(self, data: dict) -> dict:
        device = data["DcimDevice"]["edges"][0]["node"]
        return {"hostname": device["name"]["value"]}
```

## Supporting References

- **[examples.md](./examples.md)** -- Complete transform
  patterns (Python, Jinja2, hybrid, CSV)
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching) across all skills
- **[../infrahub-schema-creator/SKILL.md](../infrahub-schema-creator/SKILL.md)**
  -- Schema definitions transforms work with
- **[rules/](./rules/)** -- Individual rules by category
