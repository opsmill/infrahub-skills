---
title: Menu Hierarchy and Nesting
impact: HIGH
tags: hierarchy, nesting, children, data, group-headers
---

## Menu Hierarchy and Nesting

Impact: HIGH

Menu items can be nested to any depth using
`children.data`.

### Incorrect -- children without data wrapper

```yaml
- namespace: Dcim
  name: DeviceMenu
  children:
    - namespace: Dcim        # Wrong! Must be under `data`
      name: Servers
```

### Correct -- children with data wrapper

```yaml
- namespace: Dcim
  name: DeviceMenu
  label: Device Management
  icon: "mdi:server"
  children:
    data:                          # Required wrapper
      - namespace: Dcim
        name: InfrastructureMenu
        label: "Infrastructure"
        icon: "mdi:server"
        children:
          data:
            - namespace: Dcim
              name: Server
              label: Servers
              kind: DcimServer
              icon: mdi:server

            - namespace: Dcim
              name: Switch
              label: Switches
              kind: DcimSwitch
              icon: mdi:switch

      - namespace: Dcim
        name: TypesMenu
        label: "Types & Platforms"
        icon: "mdi:cog"
        children:
          data:
            - namespace: Organization
              name: Manufacturer
              label: Manufacturers
              kind: OrganizationManufacturer
              icon: "mdi:factory"
```

### Planning a Hierarchy

Map out the navigation structure first:

```text
Device Management
  ├── Infrastructure
  │   ├── Servers
  │   ├── Switches
  │   └── PDUs
  ├── Types & Platforms
  │   ├── Manufacturers
  │   └── Device Types
  └── Modules
      ├── Module Types
      └── Module Installations
```

### Key Rules

- `children` must contain a `data` key wrapping
  the array of child items
- Children follow the identical property structure
  (unlimited nesting depth)
- Use YAML comments for readability in large menus
  (`# --------- Section ---------`)

Reference:
[Infrahub Menu Docs](https://docs.infrahub.app)
