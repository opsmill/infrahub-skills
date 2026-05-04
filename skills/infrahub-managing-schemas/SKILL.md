---
name: infrahub-managing-schemas
description: >-
  Creates, validates, and modifies Infrahub schema YAML files — nodes, generics, attributes, relationships, and extensions.
  TRIGGER when: designing data models, adding schema nodes, validating schema definitions, planning schema migrations.
  DO NOT TRIGGER when: populating data objects, writing checks/generators/transforms, querying live data.
paths:
  - "schemas/**/*.yml"
  - "schemas/**/*.yaml"
  - "*schema*.yml"
  - "*schema*.yaml"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
argument-hint: "[namespace] [node-names...]"
metadata:
  version: 1.2.2
  author: OpsMill
---

# Infrahub Schema Creator

## Overview

Expert guidance for designing and building Infrahub
schemas. Schemas are YAML files defining nodes (concrete
types), generics (abstract base types), attributes,
relationships, and extensions.

## Project Context

Existing schemas in this project:
!`find . -name "*.yml" -path "*/schemas/*" -o -name "*schema*" -name "*.yml" 2>/dev/null | head -20`

Infrahub config (if present):
!`cat .infrahub.yml 2>/dev/null || echo "No .infrahub.yml found"`

If invoked with arguments (e.g., `/infrahub:managing-schemas Ipam Vlan VlanGroup`),
use the first argument as the namespace and remaining arguments as node names.

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

## Workflow

Follow these steps when creating or modifying a schema:

1. **Gather requirements** — Identify the node types,
   their attributes, and how they relate to each other.
   Ask about hierarchies, dropdowns, and display needs.
2. **Read relevant rules** — Read
   [rules/naming-conventions.md](./rules/naming-conventions.md)
   for naming constraints,
   [rules/attribute-defaults-and-types.md](./rules/attribute-defaults-and-types.md)
   for attribute kinds and defaults, and
   [rules/relationship-identifiers.md](./rules/relationship-identifiers.md)
   for bidirectional relationship setup.
3. **Build the schema YAML** — Start with the `$schema`
   comment and `version: "1.0"`. Define generics first
   (if any), then nodes. Apply naming, display, and
   relationship rules from step 2.
4. **Configure display properties** — Set
   `human_friendly_id`, `display_label`, and
   `order_weight` per
   [rules/display-human-friendly-id.md](./rules/display-human-friendly-id.md)
   and [rules/display-order-weight.md](./rules/display-order-weight.md).
5. **Validate** — Run `infrahubctl schema check` per
   [validation.md](./validation.md). Fix any errors
   using [rules/validation-common-errors.md](./rules/validation-common-errors.md).

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
