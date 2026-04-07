---
title: Menu File Structure
impact: CRITICAL
tags: format, apiVersion, kind, Menu, spec
---

## Menu File Structure

Impact: CRITICAL

Every menu file must follow the exact YAML structure.

### Required Fields

| Field        | Value             | Description                   |
| ------------ | ----------------- | ----------------------------- |
| `apiVersion` | `infrahub.app/v1` | Always this value             |
| `kind`       | `Menu`            | Always `Menu` for navigation  |
| `spec.data`  | list              | Array of top-level menu items |

### Correct

```yaml
# yaml-language-server:
#   $schema=https://schema.infrahub.app/infrahub/menu/latest.json
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

The menu file must be registered in `.infrahub.yml`
under the `menus:` key. Always include this as a
YAML comment in the output file so the user knows:

```yaml
# Register this file in .infrahub.yml:
#
#   menus:
#     - menus/menu-full.yml
```

### Key Rules

- Include the `$schema` comment for IDE validation
- Include `.infrahub.yml` registration comment
- Include `include_in_menu: false` advice comment
- One menu file per project typically
- The menu replaces the auto-generated sidebar
  navigation

Reference: [infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
