---
title: Common Menu Patterns
impact: LOW
tags: patterns, flat-menu, commented-items, generic-links
---

## Common Menu Patterns

**Impact: LOW (reference patterns)**

### Flat Menu (No Nesting)

For simple projects with few node types:

```yaml
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

### Direct Link to Generic Node List

```yaml
- namespace: Location
  name: AllLocations
  label: All Locations
  kind: LocationGeneric          # Shows all location types in one view
  icon: "mdi:map-marker"
```

### Commented Out Items

Use YAML comments to temporarily hide menu items:

```yaml
children:
  data:
    - namespace: Dcim
      name: Switch
      label: Switches
      kind: DcimSwitch
      icon: mdi:switch

    # - namespace: Dcim
    #   name: Interface
    #   label: Interfaces
    #   kind: DcimInterface
    #   icon: mdi:ethernet
```

Reference: [Infrahub Menu Docs](https://docs.infrahub.app)
