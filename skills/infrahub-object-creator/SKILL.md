---
name: infrahub-object-creator
description: Create and manage Infrahub object data files. Use when populating infrastructure data, creating device instances, locations, organizations, module installations, or any other data objects for an Infrahub repository.
metadata:
  version: 1.1.0
  author: OpsMill
---

# Object Creator

## Overview

Expert guidance for creating Infrahub object (data) files.
Objects are YAML files that populate schema nodes with actual
infrastructure data -- devices, locations, organizations,
modules, and more.

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

## Supporting References

- **[reference.md](./reference.md)** -- Object file format
  specification
- **[examples.md](./examples.md)** -- 15 complete object
  patterns from production repos
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching) across all skills
- **[../infrahub-schema-creator/SKILL.md](../infrahub-schema-creator/SKILL.md)**
  -- Schema definitions these objects conform to
- **[rules/](./rules/)** -- Individual rules by category
  prefix
