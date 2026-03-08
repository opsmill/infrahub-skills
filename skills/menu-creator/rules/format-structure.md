---
title: Menu File Structure
impact: CRITICAL
tags: format, apiVersion, kind, Menu, spec
---

## Menu File Structure

**Impact: CRITICAL**

Every menu file must follow the exact YAML structure.

### Required Fields

| Field | Value | Description |
|-------|-------|-------------|
| `apiVersion` | `infrahub.app/v1` | Always this value |
| `kind` | `Menu` | Always `Menu` for navigation files |
| `spec.data` | list | Array of top-level menu items |

**Correct:**

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/menu/latest.json
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceMenu
      label: Devices
      icon: "mdi:server"
      kind: DcimDevice
```

### .infrahub.yml Registration

```yaml
menus:
  - menus/menu-full.yml
```

### Key Rules

- Include the `$schema` comment for IDE validation
- One menu file per project typically
- The menu replaces the auto-generated sidebar navigation

Reference: [../common/infrahub-yml-reference.md](../../common/infrahub-yml-reference.md)
