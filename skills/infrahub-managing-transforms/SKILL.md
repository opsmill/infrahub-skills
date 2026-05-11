---
name: infrahub-managing-transforms
description: >-
  Creates Infrahub transforms that convert data into JSON, text, CSV, or device configs using Python or Jinja2 templates.
  TRIGGER when: building config generation, data export, format conversion, Jinja2 templates, artifact pipelines.
  DO NOT TRIGGER when: designing schemas, writing validation checks, creating generators, querying live data.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
argument-hint: "[transform-name] [format]"
metadata:
  version: 1.2.4
  author: OpsMill
---

# Infrahub Transform Creator

## Overview

Expert guidance for creating Infrahub transforms.
Transforms convert Infrahub data into different formats
-- JSON, text, CSV, device configs, or any text-based
output -- using Python classes or Jinja2 templates.

## Project Context

Infrahub config:
!`cat .infrahub.yml 2>/dev/null || echo "No .infrahub.yml found"`

Existing transforms:
!`find . -name "*.py" -path "*/transforms/*" -o -name "*.j2" -path "*/templates/*" 2>/dev/null | head -20`

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

## Workflow

Follow these steps when creating a transform:

1. **Choose the transform type** — Python for JSON/dict
   or complex logic, Jinja2 for text templates, hybrid
   for both. Read
   [rules/types-overview.md](./rules/types-overview.md).
2. **Write the GraphQL query** — Create a `.gql` file
   that fetches the data to transform. Read
   [../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)
   for query patterns.
3. **Implement the transform** — For Python, inherit
   from `InfrahubTransform` and implement `transform()`.
   Read [rules/python-transform.md](./rules/python-transform.md).
   For Jinja2, create a `.j2` template. Read
   [rules/jinja2-template.md](./rules/jinja2-template.md).
   For hybrid, read
   [rules/hybrid-python-jinja2.md](./rules/hybrid-python-jinja2.md).
4. **Connect to artifacts** — If the transform output
   should be stored as a file, configure artifact
   definitions. See
   [rules/artifacts-definitions.md](./rules/artifacts-definitions.md).
5. **Register in .infrahub.yml** — Add under
   `python_transforms` or `jinja2_transforms`. See
   [rules/api-reference.md](./rules/api-reference.md).
6. **Test** — Run `infrahubctl transform` or
   `infrahubctl render`. See
   [rules/testing-commands.md](./rules/testing-commands.md).

## Supporting References

- **[examples.md](./examples.md)** -- Complete transform
  patterns (Python, Jinja2, hybrid, CSV)
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching) across all skills
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**
  -- Schema definitions transforms work with
- **[rules/](./rules/)** -- Individual rules by category
