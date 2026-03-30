---
name: infrahub-schema-creator
description: >-
  Create, validate, and modify Infrahub schemas. Use when
  designing data models, creating schema nodes with
  attributes and relationships, validating schema
  definitions, or planning schema migrations for Infrahub.
metadata:
  version: 1.1.0
  author: OpsMill
---

# Infrahub Schema Creator

## Overview

Expert guidance for designing and building Infrahub
schemas. Schemas are YAML files defining nodes (concrete
types), generics (abstract base types), attributes,
relationships, and extensions.

## When to Use

- Designing new data models or schema nodes
- Adding attributes or relationships to existing schemas
- Setting up hierarchical location trees or component/parent patterns
- Configuring display properties (human_friendly_id, display_label)
- Migrating or refactoring existing schemas
- Debugging schema validation errors

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Naming | `naming-` | Namespace, node, attribute naming |
| CRITICAL | Relationships | `relationship-` | IDs, peers, component/parent |
| HIGH | Attributes | `attribute-` | Defaults, dropdowns, deprecated |
| HIGH | Hierarchy | `hierarchy-` | Hierarchical generics, parent/children |
| HIGH | Display | `display-` | human_friendly_id, order_weight |
| MEDIUM | Extensions | `extension-` | Cross-file via extensions block |
| MEDIUM | Uniqueness | `uniqueness-` | Constraint format, __value suffix |
| MEDIUM | Migration | `migration-` | Add/remove attributes, state: absent |
| LOW | Validation | `validation-` | Common errors, pre-check checklist |

## Schema File Basics

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

generics:      # Abstract base definitions (shared attributes/relationships)
  - ...
nodes:         # Concrete object types
  - ...
extensions:    # Add attributes/relationships to existing nodes from other files
  nodes:
    - ...
```

Always include the `$schema` comment for IDE validation.
Only `version` is required at the top level.

## Supporting References

- **[reference.md](./reference.md)** -- Complete property
  tables for nodes, generics, attributes, relationships
- **[examples.md](./examples.md)** -- Full schema patterns
  from production repos
- **[validation.md](./validation.md)** -- `infrahubctl`
  commands, migration strategies, pre-validation checklist
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching) across all skills
- **[rules/](./rules/)** -- Individual rules by category
  prefix
