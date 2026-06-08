---
title: Bidirectional Relationships Need Matching Identifiers
impact: CRITICAL
tags: relationship, identifier, bidirectional
---

## Bidirectional Relationships Need Matching Identifiers

Impact: CRITICAL

Both sides of a bidirectional relationship share
the same `identifier` string.

### Why it matters

Infrahub keys a relationship internally by its
`identifier`, not by the two peer kinds. When the
identifiers diverge, the engine sees two unrelated
one-directional links rather than one bidirectional
edge — writes on one side fail to surface when
queried from the other, and the UI ends up displaying
duplicate phantom relationships. The failure is
silent: no validation error fires, the data simply
behaves wrong, and the fix later requires
backfilling every existing object.

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
  identifier: "device__modules"      # Same identifier as the other side
```

**Convention:** Use `snake_case` with `__` separator:
`"parent__children"`, `"rack__devices"`,
`"tenant__racks"`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
