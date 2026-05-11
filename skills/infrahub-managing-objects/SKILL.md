---
name: infrahub-managing-objects
description: >-
  Creates and manages Infrahub object data YAML files for populating infrastructure instances — devices, locations, organizations, and modules.
  TRIGGER when: creating device instances, populating data files, defining locations or organizations, adding infrastructure objects.
  DO NOT TRIGGER when: designing schemas, writing Python checks/generators, querying live data.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
argument-hint: "[kind] [object-details...]"
metadata:
  version: 1.2.4
  author: OpsMill
---

# Object Creator

## Overview

Expert guidance for creating Infrahub object (data) files.
Objects are YAML files that populate schema nodes with actual
infrastructure data -- devices, locations, organizations,
modules, and more.

## Project Context

Existing schema files:
!`find . -name "*.yml" -path "*/schemas/*" -o -name "*schema*" -name "*.yml" 2>/dev/null | head -10`

Existing object files:
!`find . -name "*.yml" -path "*/objects/*" 2>/dev/null | head -20`

If invoked with arguments (e.g., `/infrahub:managing-objects DcimDevice spine-01`),
use the first argument as the kind and remaining arguments as object details.

## When to Use

- Creating new data files for infrastructure objects
- Populating devices, locations, organizations, or other schema nodes
- Setting up hierarchical data (location trees, tenant groups)
- Referencing related objects across files
- Managing component children (interfaces, modules)
- Organizing object files for correct load order

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | File Format | `format-` | apiVersion, kind, spec structure |
| CRITICAL | Value Mapping | `value-` | Attributes, dropdowns, references |
| HIGH | Children | `children-` | Hierarchy/component nesting |
| MEDIUM | Range | `range-` | Sequential interface expansion |
| MEDIUM | Organization | `organization-` | Naming, load order, multi-doc |
| LOW | Patterns | `patterns-` | Flat lists, devices, git repos |

## Object File Basics

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: <NodeKind>          # Schema node kind (e.g., DcimDellServer)
  data:
    - <attribute>: <value>  # List of object instances
```

`apiVersion`, `kind: Object`, `spec.kind`, and `spec.data`
are always required. Each `spec` block targets a single
node kind.

## Workflow

Follow these steps when creating object data files:

1. **Read the schema** — Identify the target node kind,
   its attributes, relationships, and whether it has
   component children or hierarchy parents.
2. **Plan the file structure** — Read
   [rules/format-structure.md](./rules/format-structure.md)
   for the required YAML structure and
   [rules/organization-load-order.md](./rules/organization-load-order.md)
   for file naming and load order conventions.
3. **Map attribute values** — Set each attribute using
   the correct value format. Read
   [rules/value-attributes.md](./rules/value-attributes.md)
   for attribute mapping and
   [rules/value-relationships.md](./rules/value-relationships.md)
   for relationship references.
4. **Handle children** — If the node has component
   children or hierarchy nesting, read
   [rules/children-components.md](./rules/children-components.md)
   and [rules/children-hierarchy.md](./rules/children-hierarchy.md).
5. **Validate** — Check YAML syntax and ensure
   referenced objects exist or are defined in earlier
   load-order files.

## Supporting References

- **[reference.md](./reference.md)** -- Object file format
  specification
- **[examples.md](./examples.md)** -- 15 complete object
  patterns from production repos
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching) across all skills
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**
  -- Schema definitions these objects conform to
- **[rules/](./rules/)** -- Individual rules by category
  prefix
