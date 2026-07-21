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

That silent behavior applies to a *fresh* load with
two diverging identifiers. A different, *loud*
failure happens when you try to **change** an
identifier that already exists in the instance — the
loader rejects it with a `not_supported` error (see
"The identifier is immutable once loaded" below).

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

### Omitting the identifier auto-generates one

Leave `identifier` off and Infrahub derives it from
the two peer kinds, sorted and lowercased — e.g.
`IpamL2Domain` + `IpamVLAN` becomes
`ipaml2domain__ipamvlan` on both sides. That still
links correctly, but the string rarely matches the
`parent__children` convention, and once loaded it is
frozen. Decide up front: set an explicit identifier
on the first load, or accept the auto-generated one
and reuse it verbatim.

### The identifier is immutable once loaded

`identifier`, `direction`, `branch`, and
`hierarchical` cannot change after a relationship
exists in the instance. Changing any of them is
rejected by `infrahubctl schema check` (and
`schema load`):

```text
Unable to load the schema:
  'not_supported': IpamL2Domain vlans None, 'not_supported': IpamVLAN l2domain None
```

Read it as `'<constraint>': <Kind> <relationship>
<message>` (trailing `None` = empty message), one
entry per side. The usual trigger: the relationship
was first loaded without an explicit identifier (so
Infrahub auto-generated one), then a schema adds a
*different* explicit `identifier`. The `kind`,
`cardinality`, and `optional` are irrelevant — they
are mutable; only the identifier changed.

To fix, set the identifier you want on the first
load, or keep the existing one — run `infrahubctl
schema check` and read the diff to see what is
already loaded. To genuinely rename it, remove the
relationship (`state: absent`), load, then re-add it
with the new identifier.

Any `kind`/`cardinality` pairing is valid as long as
both sides share one identifier and use compatible
directions — the loader enforces no kind/cardinality
matrix. `Component`(many) ↔ `Attribute`(one) loads
fine, not only `Component` ↔ `Parent`.

### Field mutability on update

| Field | On update |
| --- | --- |
| `identifier`, `direction`, `branch`, `hierarchical` | `not_supported` — remove + re-add to change |
| `peer`, `cardinality`, `min_count`, `max_count`, `optional`, `common_parent` | `validate_constraint` — allowed if existing data conforms |
| everything else (`name`, `kind`, `label`, …) | `allowed` |

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
