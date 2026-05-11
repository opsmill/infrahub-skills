---
name: infrahub-managing-schemas
description: >-
  Creates, validates, and modifies Infrahub schema YAML files — nodes, generics, attributes, relationships, and extensions.
  TRIGGER when: designing data models, adding schema nodes, validating schema definitions, planning schema migrations.
  DO NOT TRIGGER when: populating data objects, writing checks/generators/transforms, querying live data.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
argument-hint: "[namespace] [node-names...]"
metadata:
  version: 1.2.4
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
| CRITICAL | Relationships | `relationship-` | IDs, peers, component/parent, on_delete |
| HIGH | Attributes | `attribute-` | Defaults, dropdowns, computed Jinja2, branch-agnostic, deprecated |
| HIGH | Hierarchy | `hierarchy-` | Hierarchical generics, parent/children |
| HIGH | Display | `display-` | human_friendly_id, order_weight, menu placement |
| MEDIUM | Extensions | `extension-` | Cross-file via extensions block, artifact targets |
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

## Designing for Downstream Consumers

A schema node rarely lives alone. Before finalizing it,
walk through how it will be used by other parts of the
project and add the inheritance / configuration that
those features require:

| If the node will... | Add to the schema | See |
| ------------------- | ----------------- | --- |
| Be the target of an artifact (group member referenced by an `artifact_definition`) | `inherit_from: [..., CoreArtifactTarget]` on the concrete node | [rules/extension-artifact-target.md](./rules/extension-artifact-target.md) |
| Be the target of a generator (group member referenced by a `generator_definition`) | `inherit_from: [..., CoreArtifactTarget]` on the concrete node | [rules/extension-artifact-target.md](./rules/extension-artifact-target.md) |
| Appear in a custom sidebar menu | `include_in_menu: false` so the auto-menu doesn't duplicate the manual entry | [../infrahub-managing-menus/rules/schema-integration.md](../infrahub-managing-menus/rules/schema-integration.md) |
| Be cloneable as an object template | `generate_template: true` | [rules/extension-object-template.md](./rules/extension-object-template.md) |
| Be displayed with a stable name across UI lists and APIs | `human_friendly_id` and `display_label` | [rules/display-human-friendly-id.md](./rules/display-human-friendly-id.md) |

This audit is the difference between a schema that
"validates" and one that "actually works in the broader
project." Skipping it forces a schema migration once the
downstream feature is wired up — at which point the data
is already loaded.

When the task spans multiple skills (schemas + transforms,
schemas + menus, etc.), load both skills' rules together
rather than treating the boundaries as exclusive.

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
4. **Audit downstream consumers** — Walk the table in
   "Designing for Downstream Consumers" above. If any
   node will become an artifact or generator target, add
   `CoreArtifactTarget` to its `inherit_from` now, per
   [rules/extension-artifact-target.md](./rules/extension-artifact-target.md).
   Adding it later forces a schema migration on loaded data.
5. **Configure display properties** — Set
   `human_friendly_id`, `display_label`, and
   `order_weight` per
   [rules/display-human-friendly-id.md](./rules/display-human-friendly-id.md)
   and [rules/display-order-weight.md](./rules/display-order-weight.md).
6. **Validate** — Run `infrahubctl schema check` per
   [validation.md](./validation.md). Fix any errors
   using [rules/validation-common-errors.md](./rules/validation-common-errors.md).

## Production Patterns Worth Knowing

These patterns recur across the OpsMill reference
schemas (`opsmill/schema-library`,
`opsmill/infrahub-demo-dc`,
`opsmill/infrahub-solution-ai-dc`) and are easy to
miss when building from scratch:

- **Computed Jinja2 attributes** — `computed_attribute`
  always pairs with `read_only: true`; choose
  `optional` based on whether the value is
  load-bearing (display label, hfid, uniqueness) or
  informational. See
  [rules/attribute-computed-jinja2.md](./rules/attribute-computed-jinja2.md).
- **Cascade vs no-action deletes** — `on_delete:`
  is independent of `kind: Component`; pick
  `cascade` only for owned children whose existence
  has no meaning without the parent. See
  [rules/relationship-on-delete.md](./rules/relationship-on-delete.md).
- **Menu visibility** — when the project ships menu
  files in `.infrahub.yml`, set `include_in_menu:
  false` on every node and generic; otherwise hide
  abstract bases and use `menu_placement: <FullKind>`
  to group subtypes. See
  [rules/display-menu-placement.md](./rules/display-menu-placement.md).
- **Branch-agnostic identity** — `branch: agnostic`
  on attributes that must be globally unique (AS
  numbers, service names, customer IDs). See
  [rules/attribute-branch-agnostic.md](./rules/attribute-branch-agnostic.md).
- **Artifact targets** — `inherit_from:
  CoreArtifactTarget` lets a node receive rendered
  artifacts. Apply to concrete nodes, not generics.
  See
  [rules/extension-artifact-target.md](./rules/extension-artifact-target.md).
- **Object Templates** — `generate_template: true`
  enables clone-from-template UX. Independent of
  artifact targets; use only when users should
  duplicate the object as a starter for new
  instances. See
  [rules/extension-object-template.md](./rules/extension-object-template.md).

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
