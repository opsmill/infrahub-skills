---
title: Relationship Delete Behavior
impact: MEDIUM
tags: relationship, on_delete, cascade, no-action, lifecycle
---

## Relationship Delete Behavior

Impact: MEDIUM

`on_delete` controls peer lifecycle when the source
object is deleted. It is independent of
`kind: Component` — cascade behavior is opt-in and
has to be declared explicitly.

### Why it matters

The structural classification (`kind: Component`) and
the runtime lifecycle (`on_delete: cascade`) are two
separate decisions, but the naming makes them look
linked. A `kind: Component` relationship that omits
`on_delete` defaults to `no-action`, so deleting the
owner leaves every child intact as an orphan with no
back-reference — a frequent bug when refactoring
ownership. The reverse mistake hurts more: cascading
a relationship to a shared peer (an IP referenced by
multiple services, a device used by many circuits)
deletes data that other objects depend on, breaking
those other objects silently until they fail at
query time.

### Values

| Value | Behavior | When to use |
| ----- | -------- | ----------- |
| `cascade` | Deleting the source removes the peer | Owned children whose existence has no meaning without the owner (e.g., a VRRP group's IP, a circuit endpoint owned by a circuit) |
| `no-action` | Peer is preserved; the FK on the peer is unset | Cross-references between independent objects (a VIP referencing an IP that other services may also use) |

If omitted, behavior defaults to `no-action`.

### Cascade Example — Owned Child

```yaml
- name: VRRP
  namespace: Routing
  relationships:
    - name: ip_address
      peer: IpamIPAddress
      kind: Attribute
      cardinality: one
      optional: false
      on_delete: cascade           # Deleting the VRRP removes the IP
    - name: vrrp_interfaces
      peer: RoutingVRRPInterface
      kind: Component
      cardinality: many
      on_delete: cascade           # Component children deleted with parent
```

### No-Action Example — Shared Reference

```yaml
- name: VirtualIP
  namespace: ServiceLB
  relationships:
    - name: ip
      peer: IpamIPAddress
      kind: Attribute
      cardinality: one
      optional: false
      on_delete: no-action         # IP may be reused; do not auto-delete
    - name: frontend_servers
      peer: DcimGenericDevice
      kind: Component
      cardinality: many
      on_delete: no-action         # Servers are independent objects
```

### Common Pattern — Component With and Without Cascade

`kind: Component` and `on_delete` are independent
concerns:

- `kind: Component` describes the **structural
  relationship** (cascade-delete capable, identifier
  pairing, parent/child semantics in the data model).
- `on_delete: cascade` is the **runtime instruction**
  that enables actual deletion.

You can have a `kind: Component` relationship that
keeps peers alive on delete (e.g., a service with
backend servers should not delete the servers when the
service is decommissioned). Set `on_delete: no-action`
explicitly when you want this behavior.

### Decision Heuristic

Ask: *if the source object is deleted, is the peer
object meaningful on its own?*

- **Yes, peer can stand alone** → `no-action`
  (devices, IPs, locations, organizations, providers)
- **No, peer exists only because of source** →
  `cascade` (interfaces of a virtual device, BGP
  sessions of a peer group, VRRP IPs)

### Antipatterns

**Cascading shared references:**

```yaml
# WRONG — deleting one service would delete the IP,
# breaking other services that reference it
- name: ip
  peer: IpamIPAddress
  on_delete: cascade
```

**Forgetting cascade on truly owned components:**
A circuit endpoint or interface that has no purpose
without its parent should cascade. Otherwise you
accumulate orphans on every parent delete.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
