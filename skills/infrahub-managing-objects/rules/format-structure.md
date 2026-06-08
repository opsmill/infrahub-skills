---
title: Object File Structure
impact: CRITICAL
tags: format, apiVersion, kind, spec, structure
---

## Object File Structure

Impact: CRITICAL

Object files use a fixed `apiVersion` / `kind` /
`spec.kind` / `spec.data` envelope. Deviations are
rejected at load time.

### Why it matters

`infrahubctl object load` parses each document
through a strict Pydantic model: a missing
`apiVersion`, the wrong `kind`, or a `data:` list
sitting outside `spec` causes the file to be skipped
or to fail validation before any object is created.
The failure mode is silent for batch loads — the
file is reported as processed while none of its
objects reach Infrahub — so the user only notices
later when references to those objects can't
resolve.

### Required Fields

| Field | Value | Description |
| ----- | ----- | ----------- |
| `apiVersion` | `infrahub.app/v1` | Fixed string |
| `kind` | `Object` | Fixed string for data files |
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
