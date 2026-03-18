---
name: infrahub-object-creator
description: Create and manage Infrahub object data files. Use when populating infrastructure data, creating device instances, locations, organizations, module installations, or any other data objects for an Infrahub repository.
metadata:
  version: 1.1.0
  author: OpsMill
---

## Overview

Expert guidance for creating Infrahub object (data) files. Objects are YAML files that populate schema nodes with actual infrastructure data -- devices, locations, organizations, modules, and more.

## When to Use

- Creating new data files for infrastructure objects
- Populating devices, locations, organizations, or other schema nodes
- Setting up hierarchical data (location trees, tenant groups)
- Referencing related objects across files
- Managing component children (interfaces, modules)
- Organizing object files for correct load order

## Rule Categories

| Priority | Category | Prefix | Description |
|----------|----------|--------|-------------|
| CRITICAL | File Format | `format-` | apiVersion, kind: Object, spec structure, required fields |
| CRITICAL | Value Mapping | `value-` | How attributes, dropdowns, and relationship references map to schema types |
| HIGH | Children | `children-` | Hierarchical nesting, component nesting, kind specification |
| MEDIUM | Range Expansion | `range-` | Sequential interface expansion with expand_range |
| MEDIUM | File Organization | `organization-` | Naming conventions, load order, multi-document files |
| LOW | Common Patterns | `patterns-` | Flat lists, parent-child, devices, empty slots, git repos |

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

`apiVersion`, `kind: Object`, `spec.kind`, and `spec.data` are always required. Each `spec` block targets a single node kind.

## Supporting References

- **[reference.md](./reference.md)** -- Object file format specification
- **[examples.md](./examples.md)** -- 15 complete object patterns from production repos
- **[../common/infrahub-yml-reference.md](../common/infrahub-yml-reference.md)** -- .infrahub.yml project configuration
- **[../common/rules/](../common/rules/)** -- Shared rules (git integration, caching gotchas) that apply across all skills
- **[../schema-creator/SKILL.md](../schema-creator/SKILL.md)** -- Schema definitions these objects conform to
- **[rules/](./rules/)** -- Individual rules organized by category prefix
