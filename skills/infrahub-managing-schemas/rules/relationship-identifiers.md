---
title: Bidirectional Relationships Need Matching Identifiers
impact: CRITICAL
tags: relationship, identifier, bidirectional
---

## Bidirectional Relationships Need Matching Identifiers

Impact: CRITICAL

When two nodes reference each other, both sides of the
relationship MUST share the same `identifier` string.
Mismatched identifiers create duplicate relationships
instead of one bidirectional link.

**Incorrect:**

```yaml
# On Device:
- name: modules
  peer: DcimModuleInstallation
  kind: Component
  cardinality: many
  identifier: "device__modules"

# On ModuleInstallation:
- name: device
  peer: DcimGenericDevice
  kind: Parent
  cardinality: one
  optional: false
  identifier: "module__device"       # WRONG - doesn't match!
```

**Correct:**

```yaml
# On Device:
- name: modules
  peer: DcimModuleInstallation
  kind: Component
  cardinality: many
  identifier: "device__modules"

# On ModuleInstallation:
- name: device
  peer: DcimGenericDevice
  kind: Parent
  cardinality: one
  optional: false                    # Required on every kind: Parent
  identifier: "device__modules"      # MUST match the other side
```

**Convention:** Use `snake_case` with `__` separator:
`"parent__children"`, `"rack__devices"`,
`"tenant__racks"`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
