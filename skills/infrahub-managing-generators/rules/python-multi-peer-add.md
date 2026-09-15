---
title: Adding Multiple Peers to a Relationship
impact: HIGH
tags: python, relationship, add, extend, members, manager, peers
---

## Adding Multiple Peers to a Relationship

Impact: HIGH

`RelationshipManager.add()` takes **one peer per call**.
Passing a list creates a single peer whose HFID is the
list contents, which the server rejects.

### How the bug looks

```python
group.members.add(["peer-a", "peer-b", "peer-c"])
```

produces one peer object with no id and a composite HFID:

```text
[{"hfid": ["peer-a", "peer-b", "peer-c"]}]
```

The server returns "Unable to find the node" or "Invalid
HFID component count" depending on the schema.

### Anti-pattern

```python
# WRONG. Interprets the whole list as one peer.
peer_ids = ["peer-a", "peer-b", "peer-c"]
group.members.add(peer_ids)
await group.save()
```

### Correct pattern

```python
# RIGHT. .extend() calls .add() once per item.
peer_ids = ["peer-a", "peer-b", "peer-c"]
group.members.extend(peer_ids)
await group.save()
```

An explicit loop is equivalent and equally correct:

```python
for peer_id in peer_ids:
    group.members.add(peer_id)
await group.save()
```

### Two things that will catch you

**`.add()` needs a fetched manager.** Calling it before
`fetch()` raises `UninitializedError: Must call fetch() on
RelationshipManager before editing members`.

**`.add()` is already duplicate-safe.** A peer whose id or
HFID is already present is silently ignored, so no
already-present guard is needed.

The mutators are `add`, `extend` and `remove`. There is no
`.update()`.

### This does not make concurrent writes safe

`.add()` plus `.save()` sends the entire peer list, so a
second run writing the same node overwrites this one. When
any other run can write the node, see
[python-concurrent-relationship-writes.md](python-concurrent-relationship-writes.md).

Verified against Infrahub 1.11.2 and infrahub-sdk 1.23.2.
