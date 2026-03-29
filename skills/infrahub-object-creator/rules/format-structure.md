---
title: Object File Structure
impact: CRITICAL
tags: format, apiVersion, kind, spec, structure
---

## Object File Structure

Impact: CRITICAL

Every object file must follow the exact YAML structure.
Missing or misplaced fields cause silent failures.

### Required Fields

| Field | Value | Description |
| ----- | ----- | ----------- |
| `apiVersion` | `infrahub.app/v1` | Always this value |
| `kind` | `Object` | Always `Object` for data files |
| `spec.kind` | Node kind | Schema node type (e.g., `DcimDellServer`) |
| `spec.data` | list | List of object instances |

### Optional Fields

| Field | Description |
| ----- | ----------- |
| `version` | `"1.0"` -- Optional version string |

**Incorrect:**

```yaml
# Missing apiVersion
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: my-device

# Data not under spec
apiVersion: infrahub.app/v1
kind: Object
data:
  - name: my-device
```

**Correct:**

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: my-device
      status: active
```

### One Kind per Document

Each `spec` block targets a single node kind. To create
objects of different kinds, use separate YAML documents
(separated by `---`) or separate files.

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

Reference: [reference.md](../reference.md) for full format specification.
