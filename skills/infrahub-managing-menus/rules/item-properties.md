---
title: Menu Item Properties
impact: CRITICAL
tags: item, name, namespace, label, kind, path, icon, children
---

## Menu Item Properties

Impact: CRITICAL

Every menu item has required and optional properties.

### Property Reference

| Property       | Type    | Required | Description               |
| -------------- | ------- | -------- | ------------------------- |
| `name`         | string  | Yes      | Unique identifier         |
| `namespace`    | string  | Yes      | Organizational grouping   |
| `label`        | string  | No       | Display text in the UI    |
| `kind`         | string  | No       | Links to a schema node    |
| `path`         | string  | No       | Direct URL path           |
| `icon`         | string  | No       | MDI library icon          |
| `order_weight` | integer | No       | Sort position             |
| `parent`       | string  | No       | Parent menu item ref      |
| `children`     | object  | No       | Nested items under `data` |

### kind vs path

Use `kind` to link to a schema node's list view
(auto-resolves the URL):

```yaml
- namespace: Dcim
  name: Servers
  kind: DcimServer        # Auto-links to /objects/DcimServer
```

Use `path` for custom URLs (only when `kind` does
not apply):

```yaml
- namespace: Custom
  name: Dashboard
  path: /dashboard        # Direct URL
```

Never use both `kind` and `path` on the same item.

### Items Without kind or path

A menu item without `kind` or `path` serves as a
group header (non-clickable):

```yaml
- namespace: Dcim
  name: DeviceManagementMenu
  label: Device Management
  icon: "mdi:server"
  # No kind = just a header for grouping children
  children:
    data:
      - ...
```

Reference:
[Infrahub Menu Docs](https://docs.infrahub.app/topics/menu/)
