---
title: Opt Out of Tracking When Saving Upstream Nodes
impact: CRITICAL
tags: tracking, upstream, update_group_context, delete_unused_nodes
---

## Opt Out of Tracking When Saving Upstream Nodes

Impact: CRITICAL

When `generate()` modifies a node it didn't create — typically an upstream
design object, a shared resource, or any node fetched via
`self.client.get(...)` — the `.save()` call must pass
`update_group_context=False`. Otherwise the SDK silently enrolls the
upstream node in *this* generator's `CoreGeneratorGroup`.

### Why It Matters

Inside `generate()`, the SDK client runs in `TRACKING` mode. Every
`node.save()` auto-calls `add_related_nodes([self.id])` on the active
group context (`infrahub_sdk/node/node.py:973-1000`). The tracking system
then treats that node as a member of the group.

On the next run of the generator, if that upstream node isn't re-touched,
the `delete_unused_nodes=True` semantics kick in and the node is deleted.
A generator whose only intent was to flip a `role` attribute on an
existing device has just deleted the device from production.

This is the most insidious failure mode in the entire tracking system: it
looks correct on the first run and breaks silently on the second.

### The Rule

Any `.save()` on a node assigned from `self.client.get(...)`,
`self.client.filters(...)`, or similar fetch operation must pass
`update_group_context=False`:

```python
existing = await self.client.get(kind="DcimDevice", id=device_id)
existing.role.value = "spine"
await existing.save(update_group_context=False, allow_upsert=True)
```

The flag is purely additive — `allow_upsert=True` and other kwargs still
apply.

### Example

**Incorrect — upstream device joins this generator's tracking group:**

```python
async def generate(self, data: dict) -> None:
    for device_id in sorted(data["candidates"]):
        device = await self.client.get(kind="DcimDevice", id=device_id)
        device.role.value = "spine"
        await device.save(allow_upsert=True)  # silently enrolled

        iface = await self.client.create(
            kind="DcimInterfaceManagement",
            data={"device": device_id, "name": "mgmt0"},
        )
        await iface.save(allow_upsert=True)
```

On run 2, if `candidates` shrinks, the un-listed devices are deleted —
not just disconnected, *deleted from the database*.

**Correct — fetch-and-modify opts out of group context:**

```python
async def generate(self, data: dict) -> None:
    for device_id in sorted(data["candidates"]):
        device = await self.client.get(kind="DcimDevice", id=device_id)
        device.role.value = "spine"
        await device.save(
            update_group_context=False,  # ← key flag
            allow_upsert=True,
        )

        iface = await self.client.create(
            kind="DcimInterfaceManagement",
            data={"device": device_id, "name": "mgmt0"},
        )
        await iface.save(allow_upsert=True)  # iface is created — group ownership is correct
```

The newly-`.create()`'d interface stays in the group (that's correct —
the generator owns it). The pre-existing device opts out.

### Common Mistakes

- Forgetting the flag on the *first* `.save()` after a `.get()` — the
  enrollment happens on that exact line; subsequent saves don't unenroll.
- Applying the flag to `.create()` outputs — those are the nodes the
  generator legitimately owns and *should* be tracked.
- Treating "I'm only changing one attribute" as exempt — the tracking
  enrollment happens regardless of how much was modified.

### Source

- SDK: `infrahub_sdk/node/node.py:973-1000` (auto-enrollment on save).
- SDK: `infrahub_sdk/client.py:1755-1764` (group context lifecycle).
