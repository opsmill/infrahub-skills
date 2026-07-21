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

If you leave `identifier` off, Infrahub generates
one from the two peer kinds, sorted and lowercased:
`"__".join(sorted([node_kind, peer_kind])).lower()`.
Both sides derive the *same* string, so an omitted
identifier still produces a correctly-linked
bidirectional edge — for peers `IpamL2Domain` and
`IpamVLAN` the auto-generated identifier is
`ipaml2domain__ipamvlan` on both sides.

The catch: that auto-generated string rarely matches
the `parent__children` convention you would have
written by hand. Once the relationship has been
loaded once, the identifier is frozen (see below), so
decide up front — set an explicit identifier from the
very first load, or accept the auto-generated one and
reuse it verbatim everywhere.

Source: `_generate_identifier_string` in
`infrahub/core/schema/schema_branch.py`.

### The identifier is immutable once loaded

`identifier` cannot be changed after a relationship
exists in a running Infrahub instance. It is one of a
handful of relationship fields the schema loader
marks as *update: not_supported* — alongside
`direction`, `branch`, and `hierarchical`. Changing
any of them on an already-loaded relationship is
rejected by `infrahubctl schema check` (and
`schema load`) with:

```text
Unable to load the schema:
  'not_supported': IpamL2Domain vlans None, 'not_supported': IpamVLAN l2domain None
```

Read the signature as
`'<constraint>': <Kind> <relationship-name> <message>`
— the trailing `None` is just the (empty) message.
There is one entry per side because both sides carry
the same, now-conflicting, identifier.

**What actually triggers it** (this is the trap):
the relationship was first loaded *without* an
explicit identifier, so Infrahub auto-generated
`ipaml2domain__ipamvlan`. Later you add an explicit
`identifier: "l2domain__vlans"` — a *different*
string — and the loader sees an attempt to change an
immutable field. The error is not about the
relationship `kind`, `cardinality`, or `optional`;
those are all mutable. It is purely: *you tried to
rename an existing relationship's identifier.*

**The fix** — pick one:

- Set the identifier you want on the **first** load,
  before the nodes exist in the instance. Fresh
  relationships accept any identifier.
- If the relationship is already loaded, keep its
  current identifier. Query it from the live schema
  (`GET /api/schema` → the relationship's
  `identifier`) and reuse that exact value. If it was
  auto-generated, that means using
  `sorted(kinds).lower()`.
- If you genuinely must rename the identifier, that
  is a destructive migration: remove the relationship
  (`state: absent`), load, then re-add it with the
  new identifier. Treat it like renaming a column.

Verified against Infrahub v1.10.5:
`infrahubctl schema check` on the same
`IpamL2Domain`/`IpamVLAN` pair passes when the
identifier keeps its existing
`ipaml2domain__ipamvlan` value (even while flipping
`optional` from `true` to `false`) and fails with the
error above only when the identifier is changed to
`l2domain__vlans`.

Source: field `update` support flags in
`infrahub/core/schema/generated/relationship_schema.py`
(`identifier`, `direction`, `branch`, `hierarchical`
are `not_supported`); error raised in
`SchemaUpdateValidationResult._process_field` in
`infrahub/core/models.py`; string built by
`SchemaUpdateValidationError.to_string`.

### Which kind / cardinality pairings are valid

Any combination of `kind` and `cardinality` is a
valid shared-identifier bidirectional edge, provided
**both sides share one identifier** and use
compatible `direction` values (the default
`bidirectional` on both sides is always compatible).
The loader does **not** enforce a kind-to-kind or
cardinality-to-cardinality matrix — it only enforces
direction compatibility (`bidirectional`↔`bidirectional`,
or `inbound`↔`outbound` when the same kind sits on
both ends). See `validate_identifiers` in
`schema_branch.py`.

Common, verified-valid pairings:

| Side A (`kind` / `cardinality`) | Side B (`kind` / `cardinality`) | Use for |
| --- | --- | --- |
| `Component` / `many` | `Parent` / `one` (`optional: false`) | Child owned by parent; deleting the parent deletes the children |
| `Attribute` / `one` | `Attribute` or plain / `many` | A reference and its reverse collection |
| `Component` / `many` | `Attribute` / `one` | Ownership on one side, a plain back-reference on the other (valid — this is the `IvuVMHost` ↔ `IvuVirtualMachine` and `IpamL2Domain` ↔ `IpamVLAN` shape) |

The `Component`(many) ↔ `Attribute`(one) row is worth
calling out because it *looks* like it should be
`Component` ↔ `Parent`, yet loads fine. It is the
identifier — not the kind pairing — that decides
whether `schema check` passes.

**Component ↔ Parent** (owned children):

```yaml
# On Rack:
- name: devices
  peer: DcimDevice
  kind: Component
  cardinality: many
  identifier: "rack__devices"

# On Device:
- name: rack
  peer: DcimRack
  kind: Parent
  cardinality: one
  optional: false
  identifier: "rack__devices"
```

**Attribute(one) ↔ many** (reference + reverse
collection):

```yaml
# On Interface:
- name: device
  peer: DcimDevice
  kind: Attribute
  cardinality: one
  optional: false
  identifier: "device__interfaces"

# On Device:
- name: interfaces
  peer: DcimInterface
  cardinality: many          # plain (Generic) kind
  identifier: "device__interfaces"
```

**Component(many) ↔ Attribute(one)** (the case that
looks wrong but is valid):

```yaml
# On L2Domain:
- name: vlans
  peer: IpamVLAN
  kind: Component
  cardinality: many
  identifier: "l2domain__vlans"

# On VLAN:
- name: l2domain
  peer: IpamL2Domain
  kind: Attribute
  cardinality: one
  optional: false
  identifier: "l2domain__vlans"   # SAME on both sides
```

This loads cleanly on a fresh instance. It fails with
`not_supported` **only** if `IpamVLAN`/`IpamL2Domain`
already exist with a *different* identifier for this
link — see "The identifier is immutable once loaded".

### Relationship field mutability reference

When you change a field on a relationship that already
exists in the instance, the loader classifies the
change:

| Field | On update | Meaning |
| --- | --- | --- |
| `identifier`, `direction`, `branch`, `hierarchical` | `not_supported` | Rejected outright — remove + re-add to change |
| `peer`, `cardinality`, `min_count`, `max_count`, `optional`, `common_parent` | `validate_constraint` | Allowed if existing data satisfies the new rule |
| `name`, `kind`, `label`, `description`, `order_weight`, `on_delete`, `read_only`, `display`, … | `allowed` | Changed freely |

Source:
`infrahub/core/schema/generated/relationship_schema.py`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
