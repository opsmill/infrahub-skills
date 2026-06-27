---
title: yagni-custom-domain-primitives-instead-of-builtin
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, schema, ipam, vlan, builtin
---

# Rule: yagni-custom-domain-primitives-instead-of-builtin

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — Already in this codebase (built-in primitives)?

## What It Checks

Custom schemas that redefine domain primitives Infrahub already ships
built-in or that `opsmill/schema-library` provides. Most common:
custom IP address, IP prefix, IP namespace, and VLAN nodes that don't
inherit from `BuiltinIPAddress` / `BuiltinIPPrefix` /
`BuiltinIPNamespace` / `IpamVLAN`.

## Why it matters

The built-in IPAM and VLAN primitives carry platform integrations the
schema layer alone can't express: prefix-tree allocation, address
overlap detection, namespace scoping, pool/range awareness, the IPAM
sidebar views, and the IP-prefix utilization computations. A custom
`IPAddress` node ships only the attributes; everything else silently
disappears, including the IPAM API surfaces and the proposed-change
visualisations operators rely on. The cost shows up later as
hand-rolled allocation logic, missed overlaps, and divergence between
the custom schema and the platform's evolving IPAM model.

## Checks

1. A schema node with `address` or `prefix` in its name (or
   attributes called `address`, `prefix`, `ip_address`,
   `ip_prefix`, `subnet`, `cidr`) that does not have
   `inherit_from: [BuiltinIPAddress]` or `[BuiltinIPPrefix]`
   (or the `schema-library` derivatives `IpamIPAddress` /
   `IpamIPPrefix`).
2. A schema node modelling an IP namespace, VRF, or routing-instance
   container that doesn't inherit from `BuiltinIPNamespace` or
   `IpamIPNamespace`.
3. A schema node modelling a VLAN (`vlan_id`, `vid`, `tag`
   attributes) that doesn't inherit from `IpamVLAN`.
4. Two parallel definitions: one custom `MyIPAddress` node and one
   `BuiltinIPAddress`-inheriting node coexisting. Consolidate on the
   inheriting one.
5. Custom Python checks or generators reproducing IPAM behaviour
   (uniqueness within a namespace, prefix containment, overlap
   detection) that the built-in primitives would handle natively
   once adopted.

## What NOT to flag

- Domain nodes that *reference* IPAM objects via relationships
  (`device.management_ip → IpamIPAddress`) — those are correctly
  using the platform, not redefining it.
- Specialised types that legitimately extend the built-in (a
  `LoopbackAddress` node that does `inherit_from: [BuiltinIPAddress]`
  and adds two attributes). That's the pattern we want.
- Vendor-specific overlay constructs (segment IDs, EVI numbers,
  VXLAN VNIs) that are *not* VLANs in the 802.1Q sense — they're
  different primitives, not duplicates.
- L2 broadcast domain nodes whose semantics genuinely differ from
  802.1Q VLANs and whose use of `vlan_id` is incidental
  ("association tag" rather than identifier).

## Common Issues

- A repo's schema defining `MyIPAddress` with `address: IPHost`,
  `description: Text`, `status: Dropdown` — but no
  `inherit_from: [BuiltinIPAddress]`. The custom node loses prefix-
  tree integration. Replace with `inherit_from: [BuiltinIPAddress]`
  and keep only the genuinely new attributes.
- A `Subnet` node with `cidr: Text` and bespoke allocation logic in
  a generator. `inherit_from: [BuiltinIPPrefix]` provides the
  containment and allocation primitives the generator is
  reimplementing.
- A `VLAN` node with `vlan_id: Number`, `name: Text`, no
  `IpamVLAN` inheritance. The IPAM views and the standard VLAN-to-
  L3 relationship machinery are silently disabled.
- A pair of competing IP-address nodes — one inheriting
  `BuiltinIPAddress`, one not — leading to two divergent ways to
  represent the same fact.
