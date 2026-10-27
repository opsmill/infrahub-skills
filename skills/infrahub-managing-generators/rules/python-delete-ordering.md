---
title: Detach Peers Before Deleting Them
impact: MEDIUM
tags: python, relationship, delete, remove, peers, save
---

## Detach Peers Before Deleting Them

Impact: MEDIUM

A node keeps its peers in an in-memory relationship
manager. Deleting a peer through its own `.delete()` call
does not reach back into that manager to drop it there.
A `save(allow_upsert=True)` issued afterwards on a node
that still holds the deleted peer re-sends its id, because
the relationship manager only reads its own in-memory peer
list, never server state.

The upsert matters. A plain `save()` on an existing node
takes the update path, which strips relationships you never
touched, so the stale peer never reaches the payload.
`allow_upsert=True` takes the create path, which strips
nothing. Generators upsert, so this rule is about them, but
do not carry the claim over to a bare `save()`.

### When this applies

Only when the relationship is **hydrated** on the node you
save. A manager starts uninitialized, and an uninitialized
relationship is left out of the save payload altogether.
Three things hydrate one:

- `client.get(..., include=["<rel>"])`. Naming the
  relationship is what fetches it. `prefetch_relationships=True`
  on its own does **not**: a cardinality-many relationship is
  dropped from the query before that flag is ever consulted,
  and the flag then only controls how deep the peer fields go.
- `InfrahubNode.from_graphql()` on a payload that includes
  the relationship
- an explicit `await node.<rel>.fetch()`

One carve-out, and it bites: a cardinality-many relationship
whose **kind** is `Attribute` or `Parent` skips that drop and
is fetched by a plain `client.get()`. Tag-style relationships
are the common case. So "I did a plain get, nothing is
hydrated" is not safe to assume per-node; it depends on the
relationship's kind.

If none of those ran there is nothing to re-send, and
nothing to detach either: `.remove()` raises
`UninitializedError` on a manager that was never fetched.

**So the cheapest fix is not to hydrate the relationship on
the node you save.** Read whatever peer list you need from
the query payload and keep the handle you save clean. The
rest of this rule is for the case where the node genuinely
holds the relationship, which is every case where you also
have to `.add()` or `.extend()` it, since those need a
hydrated manager too.

### How the bug looks

```text
rack.interfaces holds ['iface-kept', 'iface-doomed']
iface_doomed.delete() removes it from the database
rack.save() still sends interfaces = ['iface-kept', 'iface-doomed']
```

### How it surfaces

What the server does with the stale id is
version-dependent and is not verified here. In the field
it has shown up as an error naming the deleted peer's
kind and an **upsert** mutation, which reads like a schema
problem rather than an ordering one and sends you off to
edit the schema. That is a report from a live incident
([#78](https://github.com/opsmill/infrahub-skills/issues/78)),
not a measured contract, so treat it as a way to
recognise the bug and nothing more. Do not write a check
or a failure message that assumes a specific error.

Ordering the calls so the resend never happens is the
cheap way not to find out.

### Anti-pattern

```python
# WRONG. Deletes the peers while rack still references them, then saves rack.
for iface in data["stale"]:
    node = await self.client.get(kind="DcimInterface", id=iface["id"])
    await node.delete()
await rack.save(allow_upsert=True)
```

### Correct pattern

```python
# RIGHT. Detach and save first, then delete the peers.
# The fetch names the relationship: without it the manager is
# uninitialized and .remove() raises UninitializedError.
rack = await self.client.get(
    kind="DcimRack", id=data["rack"]["id"], include=["interfaces"]
)
stale_ids = [iface["id"] for iface in data["stale"]]

for peer_id in stale_ids:
    rack.interfaces.remove(peer_id)
await rack.save(allow_upsert=True)

for peer_id in stale_ids:
    node = await self.client.get(kind="DcimInterface", id=peer_id)
    await node.delete()
```

Detaching costs nothing beyond the save the generator
already needs, and it avoids the resend outright.

### Build the id list first

Do not drive the detach loop off `rack.interfaces.peers`.
`remove()` pops from the same list `.peers` hands back, so
iterating it while removing skips every other element:
four peers leave two behind, and the next `save()` re-sends
exactly the ids this rule exists to drop. Iterating a
separate list also keeps you from detaching the peers you
still want.

### If several runs write this node

`.remove()` plus `save(allow_upsert=True)` sends the whole
peer list, which is the read-modify-write
[python-concurrent-relationship-writes.md](python-concurrent-relationship-writes.md)
calls CRITICAL. On a rack and its own interfaces that is
fine, because one run owns the node. On a node several runs
write it is not: a peer another run attached between this
fetch and this save is dropped.

There, detach server-side instead, naming only these peers:

```python
await rack.remove_relationships(
    relation_to_update="interfaces", related_nodes=stale_ids
)
```

That call does **not** touch the in-memory manager.
`rack.interfaces.peers` still holds the detached ids, so it
solves the ordering only while nothing saves that node
afterwards; a later `save(allow_upsert=True)` re-sends them
exactly as before.

If the run must also save that node, do **not** reach for
`.remove()` to paper over it. `.remove()` plus
`save(allow_upsert=True)` is the whole-list write this
section just ruled out, and pairing it with
`remove_relationships()` does not change that: the upsert
still ships every peer, so a peer another run attached
between your fetch and your save is still dropped.

Keep the relationship off the handle you save instead. Fetch
the node without naming the relationship, so its manager
stays uninitialized and the save cannot touch it, and let
`remove_relationships()` own the detach on the server. That
is the only shape here that is both correctly ordered and
safe under concurrent writers.

**Check the relationship's kind before you rely on that.**
Not naming it is only enough for a relationship the plain
fetch actually skips. An `Attribute` or `Parent` kind comes
back hydrated regardless, per the carve-out above, and
tag-style relationships are exactly the shared, contended
ones this case is about. Where the kind puts it in the
payload anyway, there is no unhydrated handle to be had:
re-fetch it into a separate handle you never save, and keep
every write to that relationship on
`add_relationships()` / `remove_relationships()`.

Verified against Infrahub 1.11.2 and infrahub-sdk 1.23.2.
