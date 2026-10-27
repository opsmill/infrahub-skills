# Infrahub Menu Examples

Working menu YAML files extracted from production
Infrahub deployments. Copy one as a starting point
and adapt the `kind:` references to your schema's
actual node names — the structures are stable; only
the kinds change.

## Contents

- [1. Flat Menu (Simple Project)](#1-flat-menu-simple-project)
- [2. Hierarchical Menu with Group Headers](#2-hierarchical-menu-with-group-headers)
- [3. Generic-Linked Menu with Subtype Children](#3-generic-linked-menu-with-subtype-children)
- [4. Full Custom Menu (Multi-Domain)](#4-full-custom-menu-multi-domain)
- [Registering the Menu](#registering-the-menu)
- [Schema Companion: Suppressing Auto-Menu Duplicates](#schema-companion-suppressing-auto-menu-duplicates)

---

## 1. Flat Menu (Simple Project)

When the project has a small number of node types
and no hierarchy is needed, a flat list of leaf
items is the right shape.

```yaml
# yaml-language-server:
#   $schema=https://schema.infrahub.app/infrahub/menu/latest.json
#
# Register this file in .infrahub.yml:
#   menus:
#     - menus/flat-menu.yml
#
# Set include_in_menu: false on schema nodes referenced below
# to prevent duplicate sidebar entries.
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: Devices
      label: Devices
      kind: DcimDevice
      icon: "mdi:server"

    - namespace: Dcim
      name: Interfaces
      label: Interfaces
      kind: DcimInterface
      icon: "mdi:ethernet"

    - namespace: Location
      name: Locations
      label: Locations
      kind: LocationGeneric
      icon: "mdi:map-marker"

    - namespace: Organization
      name: Manufacturers
      label: Manufacturers
      kind: OrganizationManufacturer
      icon: "mdi:factory"
```

---

## 2. Hierarchical Menu with Group Headers

Two top-level group headers (no `kind:`, so they're
non-clickable) each containing leaf items. This is
the canonical shape when a project has logical
domains like "Infrastructure" and "Organization".

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: InfrastructureMenu
      label: Infrastructure
      icon: "mdi:server"
      # No kind: this is a group header
      children:
        data:
          - namespace: Dcim
            name: Servers
            label: Servers
            kind: DcimServer
            icon: "mdi:server"
          - namespace: Dcim
            name: Switches
            label: Switches
            kind: DcimSwitch
            icon: "mdi:switch"
          - namespace: Dcim
            name: PDUs
            label: PDUs
            kind: DcimPdu
            icon: "mdi:power-socket"

    - namespace: Organization
      name: OrganizationMenu
      label: Organization
      icon: "mdi:domain"
      children:
        data:
          - namespace: Organization
            name: Manufacturers
            label: Manufacturers
            kind: OrganizationManufacturer
            icon: "mdi:factory"
          - namespace: Organization
            name: Providers
            label: Providers
            kind: OrganizationProvider
            icon: "mdi:transit-connection-variant"
```

---

## 3. Generic-Linked Menu with Subtype Children

A common pattern: the parent menu item links to a
generic kind (showing all subtypes in one view) AND
exposes each concrete subtype as a child for direct
access. The same `kind:` can appear at both levels.

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Location
      name: LocationsMenu
      label: Locations
      icon: "mdi:map-marker"
      kind: LocationGeneric          # Click parent → all locations
      children:
        data:
          - namespace: Location
            name: Regions
            label: Regions
            kind: LocationRegion
            icon: "mdi:earth"
          - namespace: Location
            name: Sites
            label: Sites
            kind: LocationSite
            icon: "mdi:office-building"
          - namespace: Location
            name: Rooms
            label: Rooms
            kind: LocationRoom
            icon: "mdi:door"
          - namespace: Location
            name: Racks
            label: Racks
            kind: LocationRack
            icon: "mdi:server-network"

    - namespace: Dcim
      name: Devices
      label: Devices
      kind: DcimDevice
      icon: "mdi:server"
```

---

## 4. Full Custom Menu (Multi-Domain)

A complete custom menu covering devices, types,
manufacturers, and locations — the kind of menu a
real project ships. Two levels of nesting; group
headers and leaf items mix freely.

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceManagementMenu
      label: Device Management
      icon: "mdi:server"
      children:
        data:
          - namespace: Dcim
            name: InfrastructureMenu
            label: Infrastructure
            icon: "mdi:server"
            children:
              data:
                - namespace: Dcim
                  name: Servers
                  label: Servers
                  kind: DcimServer
                  icon: "mdi:server"
                - namespace: Dcim
                  name: Switches
                  label: Switches
                  kind: DcimSwitch
                  icon: "mdi:switch"

          - namespace: Dcim
            name: TypesMenu
            label: Types & Platforms
            icon: "mdi:cog"
            children:
              data:
                - namespace: Organization
                  name: Manufacturers
                  label: Manufacturers
                  kind: OrganizationManufacturer
                  icon: "mdi:factory"
                - namespace: Dcim
                  name: DeviceTypes
                  label: Device Types
                  kind: DcimDeviceType
                  icon: "mdi:package-variant"
                - namespace: Dcim
                  name: Platforms
                  label: Platforms
                  kind: DcimPlatform
                  icon: "mdi:chip"

    - namespace: Location
      name: LocationsMenu
      label: Locations
      icon: "mdi:map-marker"
      kind: LocationGeneric
      children:
        data:
          - namespace: Location
            name: Regions
            label: Regions
            kind: LocationRegion
            icon: "mdi:earth"
          - namespace: Location
            name: Sites
            label: Sites
            kind: LocationSite
            icon: "mdi:office-building"
          - namespace: Location
            name: Racks
            label: Racks
            kind: LocationRack
            icon: "mdi:server-network"

    - namespace: Organization
      name: OrganizationMenu
      label: Organization
      icon: "mdi:domain"
      children:
        data:
          - namespace: Organization
            name: Manufacturers
            label: All Manufacturers
            kind: OrganizationManufacturer
            icon: "mdi:factory"
          - namespace: Organization
            name: Providers
            label: All Providers
            kind: OrganizationProvider
            icon: "mdi:transit-connection-variant"
          - namespace: Organization
            name: Tenants
            label: Tenants
            kind: OrganizationTenant
            icon: "mdi:account-group"
```

---

## Registering the Menu

In `.infrahub.yml`:

```yaml
menus:
  - menus/menu-full.yml
```

The key is **`menus:` (plural)**. A singular `menu:`
is rejected by the `.infrahub.yml` validator as
`extra_forbidden` — see
[rules/format-structure.md](./rules/format-structure.md).

Multiple files are allowed; each is loaded
independently and merged in the order listed.

---

## Schema Companion: Suppressing Auto-Menu Duplicates

A custom menu doesn't replace the auto-generated
sidebar — it sits next to it. Without intervention,
every node referenced from the custom menu also
appears in the auto-menu under its namespace, so
users see two entries for the same thing.

For every node listed in the custom menu, set
`include_in_menu: false` in the schema:

```yaml
# In schemas/dcim.yml
nodes:
  - name: Server
    namespace: Dcim
    include_in_menu: false           # Suppress auto-menu entry
    # ... rest of the node definition

  - name: Switch
    namespace: Dcim
    include_in_menu: false
    # ...
```

For full coverage, set it on every node and generic
the custom menu references. See
[rules/schema-integration.md](./rules/schema-integration.md)
for the full pattern and
[../infrahub-managing-schemas/rules/display-menu-placement.md](../infrahub-managing-schemas/rules/display-menu-placement.md)
for the related `menu_placement:` knob that controls
where auto-menu entries land when they're not
suppressed.
