---
title: Concurrent Writers on a Shared Relationship
impact: CRITICAL
tags: python, relationship, concurrency, add_relationships, shared-objects, lost-update
---

## Concurrent Writers on a Shared Relationship

Impact: CRITICAL

`.add()` mutates an in-memory peer list and `save()` sends
**all of it**, not a delta. Two generator runs that both
fetched the same node before either saved will each send
their own full list, and the second one lands on top of the
first.

Event-triggered generators fan out one run per created
node, so several runs writing one shared group is the
normal case during a bulk load, not an edge case.

### How the bug looks

Two writers, each holding the same fetched group:

```text
writer A sends members = ['peer-existing', 'peer-from-A']
writer B sends members = ['peer-existing', 'peer-from-B']
```

Whichever lands second is the final member list. The other
peer is gone. **Both runs log success.** Nothing errors,
and no unit test can see it, because the loss happens
between two processes.

### Anti-pattern

```python
# WRONG when any other run can write this node.
for peer in peers:
    group.members.add(peer)
await group.save(allow_upsert=True)
```

A fetch-diff guard in front of this does not help. The read
and the write are separate round trips, so the guard is
inside the race window, not outside it.

### Correct pattern

```python
# RIGHT. One server-side RelationshipAdd naming only these peers.
await group.add_relationships(
    relation_to_update="members",
    related_nodes=[p.id for p in peers],
)
```

`remove_relationships()` is the symmetric operation.

### `related_nodes` takes IDs, not nodes

The signature is `related_nodes: list[str]`. The mutation
is built by string interpolation, so a node object is
rendered as its display form and shipped inside the `id`
field **without any error**:

```text
nodes: [{ id: "TestGroup (PEER-OBJ-ID) " }]
```

The failure surfaces later as an unresolvable id. Pass
`peer.id`, not `peer`.

### No pre-read guard is needed

The server saves a peer only if it is not already attached,
so re-running is safe and a redundant run leaves the branch
diff unchanged. Drop the fetch-diff guard rather than
porting it.

### Scope

**Cardinality-many only.** On a cardinality-one
relationship that already has a peer, the mutation raises
`'<name>' is a cardinality-one relationship and already has
a peer`. Use `.save()` there.

`add_relationships()`/`remove_relationships()` have
existed with this exact signature since `infrahub-sdk`
v1.0.0 -- the body is byte-identical at v1.0.0, v1.13.0 and
v1.23.2, only the docstring was added later. No meaningful
version floor applies within the 1.x line.

The **server-side** `RelationshipAdd` behaviour this rule
relies on (naming only its own peers) is verified against
Infrahub **1.11.2** specifically. That is a separate claim
from the SDK method's availability above, about a
different piece of software -- not a statement about
which Infrahub server version first shipped
`RelationshipAdd`.

### Tracking

`add_relationships()` does not add the node to the run's
tracking group, which `save()` always does. That is a
second reason to prefer it on a shared node, and it carries
a trade. See
[tracking-idempotent.md](tracking-idempotent.md#three-ways-to-honour-it).

Verified against Infrahub 1.11.2 and infrahub-sdk 1.23.2.
