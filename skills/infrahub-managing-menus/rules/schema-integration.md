---
title: Schema Integration
impact: MEDIUM
tags: schema, include_in_menu, kind-links
---

## Schema Integration

Impact: MEDIUM

When using a custom menu, configure schema nodes
to prevent duplicate menu entries.

### Set include_in_menu: false

When you use a custom menu, set
`include_in_menu: false` on all schema nodes that
appear in the menu. Without this, Infrahub generates
auto-menu entries alongside your custom menu,
creating duplicates.

Always include this advice as a YAML comment at the
top of the menu file so the user sees it:

```yaml
# To prevent duplicate menu entries, set
# include_in_menu: false on schema nodes that
# appear in this menu:
#
#   nodes:
#     - name: Server
#       namespace: Dcim
#       include_in_menu: false
```

### kind Auto-Resolution

The `kind` property on menu items auto-resolves to
the correct URL for the node's list view:

```yaml
- namespace: Location
  name: AllLocations
  label: All Locations
  kind: LocationGeneric    # Shows all types in one view
  icon: "mdi:map-marker"
```

This is preferred over `path` because it stays
correct even if URL patterns change.

Reference:
[managing-schemas](../../infrahub-managing-schemas/SKILL.md)
