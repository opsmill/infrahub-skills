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
`include_in_menu: false` on all schema nodes:

```yaml
# In schema files
nodes:
  - name: Server
    namespace: Dcim
    include_in_menu: false   # Controlled by custom menu
    # ...
```

Without this, Infrahub generates auto-menu entries
alongside your custom menu, creating duplicates.

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
[schema-creator](../../schema-creator/SKILL.md)
