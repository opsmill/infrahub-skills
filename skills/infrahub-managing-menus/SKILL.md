---
name: infrahub-managing-menus
description: >-
  Creates Infrahub custom navigation menus for the web UI sidebar, organizing node types into logical groups.
  TRIGGER when: designing sidebar menus, grouping node types in UI, customizing Infrahub web interface navigation.
  DO NOT TRIGGER when: designing schemas, writing checks or transforms, populating data objects.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
argument-hint: "[menu-structure-description]"
metadata:
  version: 1.2.4
  author: OpsMill
---

# Infrahub Menu Creator

## Overview

Expert guidance for creating Infrahub custom menus.
Menus control the left-side navigation in the web
interface, organizing schema node types into a custom
hierarchy.

## Project Context

Existing menu files:
!`find . -name "*.yml" -path "*/menus/*" 2>/dev/null | head -10`

Schema files (to identify available node types):
!`find . -name "*.yml" -path "*/schemas/*" -o -name "*schema*" -name "*.yml" 2>/dev/null | head -10`

## When to Use

- Designing navigation menus for the Infrahub web UI
- Organizing node types into logical groups
  and hierarchies
- Adding icons and labels to menu items
- Setting up group headers (non-clickable)
  with nested children
- Configuring schema nodes to use custom menus
  instead of auto-generated ones

## Rule Categories

| Priority | Category   | Prefix       | Description                  |
| -------- | ---------- | ------------ | ---------------------------- |
| CRITICAL | Format     | `format-`    | apiVersion, kind, spec       |
| CRITICAL | Properties | `item-`      | name, namespace, label, kind |
| HIGH     | Hierarchy  | `hierarchy-` | Nesting, group headers, data |
| HIGH     | Icons      | `icons-`     | MDI icon reference, choices  |
| MEDIUM   | Schema     | `schema-`    | include_in_menu, kind links  |
| LOW      | Patterns   | `patterns-`  | Flat menu, comments, links   |

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
      kind: DcimDevice        # Links to schema node list view
```

`apiVersion`, `kind: Menu`, and `spec.data` are always
required. Each menu item needs `name` and `namespace`.

## Workflow

Follow these steps when creating a menu:

1. **Gather requirements** — Ask what schema nodes
   exist, how they should be grouped, and whether
   the user wants flat or hierarchical navigation.
2. **Read relevant rules** — Read `rules/format-structure.md`
   for the required YAML structure, `rules/item-properties.md`
   for item fields, and `rules/hierarchy-nesting.md`
   if nesting is needed. Read `rules/icons-reference.md`
   to pick appropriate MDI icons.
3. **Generate the menu YAML** — Start with the
   `$schema` comment and `apiVersion`/`kind`/`spec`
   structure. Apply rules from step 2.
4. **Add registration and schema guidance** — Every
   menu file output must include:
   - A YAML comment block showing how to register
     the file in `.infrahub.yml` under the `menus:`
     key (see `rules/format-structure.md`)
   - A YAML comment block advising to set
     `include_in_menu: false` on every schema node
     that appears in the custom menu, to prevent
     duplicate sidebar entries
     (see `rules/schema-integration.md`)

   Include these as comments at the top of the file,
   before the `---` document separator. This ensures
   the user sees the guidance alongside the menu
   definition.

## Supporting References

- **[infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[common/rules/](../infrahub-common/rules/)**
  -- Shared rules (git integration, caching gotchas)
  that apply across all skills
- **[managing-schemas](../infrahub-managing-schemas/SKILL.md)**
  -- Schema node kinds that menus link to
- **[rules/](./rules/)**
  -- Individual rules organized by category prefix
