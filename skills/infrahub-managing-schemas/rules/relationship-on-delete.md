---
title: Relationship Delete Behavior
impact: MEDIUM
tags: relationship, on_delete, cascade, no-action, lifecycle
---

## Relationship Delete Behavior

Impact: MEDIUM

`on_delete` controls what happens to peers when the
source node is deleted. When a relationship omits it,
Infrahub fills it in from the relationship kind at
schema load:

| Relationship kind | Default when `on_delete` is omitted |
| ----------------- | ----------------------------------- |
| `Component` | `cascade` |
| Every other kind | `no-action` |

The schema Infrahub serves carries the filled-in value.

### Why it matters

A `kind: Component` relationship that omits `on_delete`
resolves to `cascade`, so deleting the owner deletes
every peer. That is right for owned children and wrong
for shared peers: VLANs on an interface, or servers
behind a service, are deleted with the owner, and the
nodes that still depend on them break silently until
they fail at query time. The reverse mistake is
quieter. An owned child modelled as `Generic` or
`Attribute` with no `on_delete` resolves to
`no-action`, so deleting the owner leaves the child
behind as an orphan.

Set `on_delete` explicitly on every `kind: Component`
relationship, including when you want `cascade`. The
YAML then states the delete behavior, and a reader
does not have to know the kind-based default.

### Values

| Value | Behavior | When to use |
| ----- | -------- | ----------- |
| `cascade` | Deleting the source removes the peer | Owned children whose existence has no meaning without the owner (e.g., a VRRP group's IP, a circuit endpoint owned by a circuit) |
| `no-action` | Peer is preserved; the FK on the peer is unset | Cross-references between independent objects (a VIP referencing an IP that other services may also use) |

### Cascade Example: Owned Child

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

### No-Action Example: Shared Reference

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
      on_delete: no-action         # Overrides the Component cascade; servers are independent
```

### Common Pattern: Component Without Cascade

`kind` sets the default, and an explicit `on_delete`
overrides it:

- `kind: Component` describes the **structural
  relationship** (identifier pairing, parent/child
  semantics in the data model). Left alone, it also
  deletes the peers with the owner.
- `on_delete: no-action` on a `kind: Component`
  relationship keeps the peers when the owner is
  deleted.

A service with backend servers should not delete the
servers when the service is decommissioned. Model it
as `kind: Component` with `on_delete: no-action`, as
the `frontend_servers` example above does.

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
# WRONG: deleting one service would delete the IP,
# breaking other services that reference it
- name: ip
  peer: IpamIPAddress
  on_delete: cascade
```

**Omitting `on_delete` on a Component relationship to
a shared peer:** with no `on_delete`, the relationship
cascades, so deleting the owner deletes the shared
peer. Set `on_delete: no-action`.

**Leaving an owned child without cascade:** a circuit
endpoint or interface that has no purpose without its
parent should cascade. As `kind: Component` with no
`on_delete` it does. Modelled as `Generic` or
`Attribute`, it needs `on_delete: cascade`, or every
parent delete leaves orphans.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
