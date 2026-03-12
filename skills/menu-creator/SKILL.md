---
name: infrahub-menu-creator
description: Create and manage Infrahub custom menus. Use when designing navigation menus, organizing node types in the UI, or customizing the Infrahub web interface sidebar.
---

## Overview

Expert guidance for creating Infrahub custom menus. Menus control the left-side navigation in the web interface, organizing schema node types into a custom hierarchy.

## When to Use

- Designing navigation menus for the Infrahub web UI
- Organizing node types into logical groups and hierarchies
- Adding icons and labels to menu items
- Setting up group headers (non-clickable) with nested children
- Configuring schema nodes to use custom menus instead of auto-generated ones

## Rule Categories

| Priority | Category | Prefix | Description |
|----------|----------|--------|-------------|
| CRITICAL | File Format | `format-` | apiVersion, kind: Menu, spec structure |
| CRITICAL | Item Properties | `item-` | name, namespace, label, kind, path, icon, children |
| HIGH | Hierarchy | `hierarchy-` | Nesting children, group headers, children.data wrapping |
| HIGH | Icons | `icons-` | MDI icon reference, common icon choices |
| MEDIUM | Schema Integration | `schema-` | include_in_menu: false, kind links |
| LOW | Patterns | `patterns-` | Flat menu, commented items, direct links |

## Menu File Basics

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceMenu
      label: "Devices"
      icon: "mdi:server"
      kind: DcimDevice              # Links to schema node list view
```

`apiVersion`, `kind: Menu`, and `spec.data` are always required. Each menu item needs `name` and `namespace`.

## Supporting References

- **[../common/infrahub-yml-reference.md](../common/infrahub-yml-reference.md)** -- .infrahub.yml project configuration
- **[../common/rules/](../common/rules/)** -- Shared rules (git integration, caching gotchas) that apply across all skills
- **[../schema-creator/SKILL.md](../schema-creator/SKILL.md)** -- Schema node kinds that menus link to
- **[rules/](./rules/)** -- Individual rules organized by category prefix
