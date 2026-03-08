---
title: File Organization and Load Order
impact: MEDIUM
tags: organization, naming, load-order, dependencies
---

## File Organization and Load Order

**Impact: MEDIUM**

Objects must be loaded in dependency order. A device can't reference a rack that hasn't been created yet.

### Naming Convention

Use numeric prefixes for load order:

```
objects/
  01_manufacturers.yml          # Base data first (no dependencies)
  02_organizations.yml          # Groups/tenants
  03_device_types.yml           # Types (depend on manufacturers)
  04_module_types.yml           # Module types (depend on manufacturers)
  04a_module_bay_templates.yml  # Bay templates (depend on device types)
  05_locations.yml              # Location hierarchy
  06_devices.yml                # Devices (depend on types, locations)
  06_module_installations.yml   # Module installs (depend on devices, bays, types)
  07_empty_slots.yml            # Empty slots (depend on devices, bays)
  git-repo/
    local-dev.yml               # Git repo config for local development
```

### Dependency Order

1. **Independent objects**: Manufacturers, groups, tenant groups
2. **Type definitions**: Device types, module types, platforms
3. **Templates**: Module bay templates, interface templates
4. **Locations**: Regions > Sites > Rooms > Racks (hierarchy auto-resolves)
5. **Instances**: Devices, modules, installations
6. **Metadata**: Tags, empty slots, connections

### Multi-Document Files

A single YAML file can contain multiple documents separated by `---`:

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: SecurityFirewall
  data:
    - name: corp-firewall

---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: cisco-switch-01
```

### Bootstrap Files Must Live Outside `objects/`

When `.infrahub.yml` specifies `objects: - objects`, Infrahub auto-imports **every** YAML file in that directory during git sync. Files that define infrastructure config (like `CoreRepository` or `CoreReadOnlyRepository` definitions) will be imported as objects, which can cause validation errors or circular dependencies.

**Incorrect -- bootstrap file inside objects/:**

```
objects/
  git-repo/
    local-dev.yml          # CoreReadOnlyRepository definition
  01_manufacturers.yml     # Will ALL be auto-imported during sync
```

**Correct -- bootstrap files in a separate directory:**

```
bootstrap/
  local-dev-repo.yml       # Loaded manually, never auto-imported
objects/
  01_manufacturers.yml     # Only real data objects here
```

### .infrahub.yml Registration

```yaml
objects:
  - objects              # Loads all files in the objects/ directory recursively
```

Reference: [../common/infrahub-yml-reference.md](../../common/infrahub-yml-reference.md) | See also: [deployment-git-integration.md](../../common/rules/deployment-git-integration.md)
