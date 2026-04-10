---
title: File Organization and Load Order
impact: MEDIUM
tags: organization, naming, load-order, dependencies
---

## File Organization and Load Order

Impact: MEDIUM

Objects must be loaded in dependency order. A device can't
reference a rack that hasn't been created yet.

### Naming Convention

Use numeric prefixes for load order:

```text
objects/
  01_manufacturers.yml          # Base data (no deps)
  02_organizations.yml          # Groups/tenants
  03_device_types.yml           # Types (need mfgs)
  04_module_types.yml           # Module types
  04a_module_bay_templates.yml  # Bay templates
  05_locations.yml              # Location hierarchy
  06_devices.yml                # Devices
  06_module_installations.yml   # Module installs
  07_empty_slots.yml            # Empty slots
  git-repo/
    local-dev.yml               # Git repo config
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

When `.infrahub.yml` specifies `objects: - objects`,
Infrahub auto-imports **every** YAML file in that directory
during git sync. Files that define infrastructure config
(like `CoreRepository` or `CoreReadOnlyRepository`
definitions) will be imported as objects, which can cause
validation errors or circular dependencies.

**Incorrect -- bootstrap file inside objects/:**

```text
objects/
  git-repo/
    local-dev.yml          # CoreReadOnlyRepository def
  01_manufacturers.yml     # Will ALL be auto-imported
```

**Correct -- bootstrap files in a separate directory:**

```text
bootstrap/
  local-dev-repo.yml       # Loaded manually, never auto
objects/
  01_manufacturers.yml     # Only real data objects here
```

### .infrahub.yml Registration

```yaml
objects:
  - objects              # Loads all files in the objects/ directory recursively
```

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
| See also:
[deployment-git-integration.md](../../infrahub-common/rules/deployment-git-integration.md)
