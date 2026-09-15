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
A `save()` issued afterwards on a node that still holds
the deleted peer re-sends its id, because the relationship
manager only reads its own in-memory peer list, never
server state.

### How the bug looks

```text
rack.interfaces holds ['iface-kept', 'iface-doomed']
iface_doomed.delete() removes it from the database
rack.save() still sends interfaces = ['iface-kept', 'iface-doomed']
```

What the server does with the stale id is
version-dependent and was not observed here, so do not
write a check or a message that assumes a specific error.
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
for iface in rack.interfaces.peers:
    rack.interfaces.remove(iface.id)
await rack.save(allow_upsert=True)

for iface in data["stale"]:
    node = await self.client.get(kind="DcimInterface", id=iface["id"])
    await node.delete()
```

Detaching costs nothing beyond the save the generator
already needs, and it is the only ordering that avoids the
resend outright.

In testing, a capable model reasoned its way to this
ordering unprompted, without having read this rule. Treat
this page as a reminder of a real gotcha, not as guidance a
model is otherwise likely to miss.

Verified against Infrahub 1.11.2 and infrahub-sdk 1.23.2.
