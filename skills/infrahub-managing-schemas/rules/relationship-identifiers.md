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

Leave `identifier` off and Infrahub derives it on each
side independently from that side's own kind and its
peer kind, sorted and lowercased. When both peers are
concrete and mirror each other — `IpamL2Domain` ↔
`IpamVLAN` — both sides derive the same
`ipaml2domain__ipamvlan` and the link forms correctly.
The string rarely matches the `parent__children`
convention, and once loaded it is frozen.

Auto-generation is only safe when both sides'
`(kind, peer)` pairs mirror each other. When one side
peers a **generic** — e.g. `Device.interfaces →
DcimInterface` while `Interface.device →
DcimGenericDevice` — each side derives a *different*
string and the link silently splits into the two
phantom edges this rule exists to prevent. With a
generic on either peer, set the identifier explicitly
on both sides.

Decide up front: set an explicit identifier on the
first load, or — concrete peers only — accept the
auto-generated one and reuse it verbatim.

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

Read it as `'<error_type>': <Kind> <relationship>
<message>` (here the error type is `not_supported` and
the trailing `None` is an empty message), one entry
per side. The usual trigger: the relationship
was first loaded without an explicit identifier (so
Infrahub auto-generated one), then a schema adds a
*different* explicit `identifier`. Here `kind`,
`cardinality`, and `optional` are not what triggered
the error — only the identifier changed. They carry
their own, looser update rules; see the table below.

To fix, reuse the identifier already loaded rather
than changing the forward side. Recover its value from
the schema file or its git history, from the running
instance (`GET /api/schema`), or — for an
auto-generated one — by re-deriving it per side from
`(kind, peer)` sorted and lowercased. `schema check`
will not reveal it: when the identifier differs the
command fails with `not_supported` before printing a
diff. To genuinely rename an identifier, remove the
relationship (`state: absent`), load, then re-add it
with the new identifier.

### Field mutability on update

| Field | On update |
| --- | --- |
| `identifier`, `direction`, `branch`, `hierarchical` | `not_supported` — remove + re-add to change |
| `peer`, `cardinality`, `min_count`, `max_count`, `optional`, `common_parent` | `validate_constraint` — allowed only if existing data still conforms |
| `name`, `label`, `order_weight`, … | `allowed` |
| `kind` | `allowed` in general, but changing *into* `Parent` must satisfy the Parent constraints (`cardinality: one`, `optional: false`) or the load fails |
| `state` | `not_applicable` — `state: absent` removes the relationship rather than updating a field |

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
