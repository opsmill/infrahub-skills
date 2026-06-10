---
title: File Organization and Load Order
impact: MEDIUM
tags: organization, naming, load-order, dependencies
---

## File Organization and Load Order

Impact: MEDIUM

Object files are loaded in dependency order via
numeric filename prefixes (`01_`, `02_`, …) so that
referenced objects already exist when a later file
points at them.

### Why it matters

`infrahubctl object load` resolves
`human_friendly_id` references at insert time, not
in a deferred pass. A device file referencing a rack
that hasn't been loaded yet fails the entire batch
with an HFID lookup error — there's no second-pass
retry. Numeric prefixes give the loader a
deterministic order across the directory, so the
fix-up loop ("add the missing parent, re-run") stays
predictable instead of depending on filesystem
ordering, which varies by platform.

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

### Bootstrap Files Live Outside `objects/`

When `.infrahub.yml` specifies `objects: - objects`,
Infrahub auto-imports every YAML file in that
directory on every git sync. Bootstrap definitions
(`CoreRepository`, `CoreReadOnlyRepository`,
one-time seed data) re-apply on each sync — which
overwrites user-side edits made through the UI and
can recreate circular dependencies the user manually
broke. Keeping them in a separate directory means
they're loaded once, by hand, and stay out of the
sync loop.

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
