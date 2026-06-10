---
title: Schema Integration
impact: MEDIUM
tags: schema, include_in_menu, kind-links
---

## Schema Integration

Impact: MEDIUM

A custom menu doesn't replace the auto-generated
sidebar; it sits next to it. Schema nodes need
`include_in_menu: false` to opt out of the
auto-menu, or the user sees both entries.

### Why it matters

Infrahub builds the sidebar by merging custom menus
with auto-menus derived from the schema. The merge
is additive — neither side dedupes against the
other — so every node referenced by a custom item
that hasn't set `include_in_menu: false` shows up
twice: once in the custom hierarchy, once at the
namespace root. Users typically report this as "my
menu is weird" without realizing both entries are
working as designed; the fix is on the schema side,
which is why this rule lives in `managing-menus`
but acts on `managing-schemas`.

### Set include_in_menu: false

Set `include_in_menu: false` on every schema node
that appears in the custom menu. Without it, the
auto-menu emits a duplicate entry alongside the
custom one.

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
