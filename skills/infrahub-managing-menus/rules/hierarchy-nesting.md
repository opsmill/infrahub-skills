---
title: Menu Hierarchy and Nesting
impact: HIGH
tags: hierarchy, nesting, children, data, group-headers
---

## Menu Hierarchy and Nesting

Impact: HIGH

Nested menu items live under `children.data`, never
directly under `children`.

### Why it matters

The menu schema models children as an object that
carries pagination metadata alongside the `data`
list — the same shape every paginated Infrahub
GraphQL response uses. Putting a bare list under
`children` makes the parser reject that branch; the
sidebar renders the parent as a clickable leaf with
no children, which looks to the user like the
sub-items "disappeared". The wrapper is also what
lets future versions extend children with filtering
or pagination without reshaping existing menu files.

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

- `children` is the wrapper; `data` inside it
  carries the list of child items
- Children follow the identical property structure
  (unlimited nesting depth)
- Use YAML comments for readability in large menus
  (`# --------- Section ---------`)

Reference:
[Infrahub Menu Docs](https://docs.infrahub.app)
