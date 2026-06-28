---
title: yagni-imperative-allocation-vs-resource-pool
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, generator, resource-pool, ipam
---

# Rule: yagni-imperative-allocation-vs-resource-pool

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — Is there a built-in primitive (resource pool)?

## What It Checks

Generators that allocate a scarce resource — a subnet, an IP, a VLAN
ID, an interface, a port number — with imperative Python (`ipaddress`
subnet math, `random` selection, or a hand-written
"scan-for-the-first-free-one" loop) when Infrahub's built-in resource
pools already hand out the next free value declaratively. Pools are a
built-in primitive: `CoreIPPrefixPool`, `CoreIPAddressPool`,
`CoreNumberPool`, and the SDK's `allocate_next_ip_prefix` /
`allocate_next_ip_address`. Reinventing the allocator in Python is the
same shape as reinventing an IPAM node — see
[yagni-custom-domain-primitives-instead-of-builtin](./yagni-custom-domain-primitives-instead-of-builtin.md).

## Why it matters

A resource pool is the platform's source of truth for "what's still
free." When a generator computes the next subnet with
`ip_network(...).subnets(prefixlen_diff=1)` or picks a port with
`random.randint(...)` plus a Python filter loop, the allocation logic
lives outside the pool — so two concurrent runs can hand out the same
value, the UI shows no utilization, and nothing reserves what the
generator just consumed. Pools give you atomic next-free allocation,
visible utilization, idempotent reservation tied to the allocating
object, and exhaustion errors instead of silent collisions. The Python
form re-implements all of that, worse, and is invisible to operators.

The tell is almost always self-evident in the same file: the generator
*already* allocates some resources from a pool and then drops to
imperative math for one more. If the pool was right for VLANs and
prefixes, it's right for the port too.

## Checks

1. Generator that imports `ipaddress` and calls `.subnets(...)`,
   `.hosts(...)`, or arithmetic on `network_address` to carve a child
   prefix/IP, then `client.create(kind="IpamIPPrefix" / "IpamIPAddress")`
   with the computed value — instead of `allocate_next_ip_prefix` /
   `allocate_next_ip_address` against a pool.
2. Generator that picks a resource with `random.choice` /
   `random.randint` and a `next((x for x in peers if ...free...))`
   scan loop, rather than allocating from a `CoreNumberPool` or
   filtering server-side and reserving.
3. Generator that maintains its own "used set" / counter to avoid
   collisions (`used_ids = set(); while candidate in used_ids: ...`)
   — that bookkeeping is exactly what a pool does.
4. Strong corroborating signal: the **same generator** already uses a
   pool (`allocate_next_ip_*`, a `CoreIPPrefixPool` / `CoreNumberPool`
   reference) for a different resource, and only one allocation path
   was left imperative.

## What NOT to flag

- Pure reporting/derivation that computes an address for *display or
  config rendering* without persisting an allocation (no `create` of an
  IPAM object follows the math).
- Algorithms that need a deterministic, position-derived value rather
  than "next free" — e.g. a router-id that must equal the loopback,
  a broadcast/network address derived from a known prefix, subnet math
  used only to validate that a given address falls in range.
- One-time bootstrap/seed generators (under `bootstrap/`, `seed/`,
  `demo/`) that lay down the pools themselves or seed fixed initial
  ranges.
- Cases where no suitable pool kind exists for the resource and a pool
  cannot model it (rare — verify before assuming).

## Common Issues

- A generator that does `prefix.subnets(prefixlen_diff=1)` to split a
  block into underlay/VTEP halves and `client.create` each — replace
  with two `allocate_next_ip_prefix` calls against an
  `CoreIPPrefixPool` so utilization is tracked and re-runs are
  idempotent.
- `self.index = random.randint(1, 2)` followed by a Python loop over
  interface peers looking for `status == "free"` — the free-port
  selection is a `CoreNumberPool` (or a server-side
  `status__value: "free"` filter plus a reservation), not a dice roll.
- A file that allocates VLANs and prefixes from pools correctly, then
  hand-rolls port assignment. The inconsistency is the finding: lift
  the last allocation onto the same pool mechanism.
