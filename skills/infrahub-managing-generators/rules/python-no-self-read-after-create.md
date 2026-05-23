---
title: Don't Re-fetch What You Just Created
impact: MEDIUM
tags: performance, N+1, store, race-window
---

## Don't Re-fetch What You Just Created

Impact: MEDIUM

After `obj = await self.client.create(kind="X", ...)`, do not call
`await self.client.get(kind="X", id=obj.id)` later in the same
`generate()`. The local `obj` is already the canonical reference — a
fresh `.get()` is wasted work and may see stale read-replica data.

### Why It Matters

Two problems with self-reads:

1. **N+1 cost.** Each `.get()` is one HTTP round-trip. In a loop that
   creates and then re-fetches, you pay 2× the network cost for the
   same data.
2. **Read-replica staleness.** Infrahub may serve `.get()` from a
   read-replica that hasn't seen the write yet. The fresh fetch can
   return an object missing fields you just set on the local instance.

The local SDK object is always correct because it represents *the write
you just performed*. Subsequent operations should use it directly or
pass it via `self.store.set(...)` / `self.store.get(...)` for
inter-object reference.

### The Rule

Reuse the local SDK object returned by `.create()`. If you need it later
in the function (e.g., to set up a relationship), capture it once or use
`self.store`.

### Example

**Incorrect — re-fetches what was just created:**

```python
async def generate(self, data: dict) -> None:
    for spec in sorted(data["device_specs"], key=lambda s: s["name"]):
        device = await self.client.create(
            kind="DcimDevice", data={"name": spec["name"]},
        )
        await device.save(allow_upsert=True)

        # Wasted round-trip; may see stale data
        fresh = await self.client.get(
            kind="DcimDevice", id=device.id,
        )
        iface = await self.client.create(
            kind="DcimInterface",
            data={"device": fresh.id, "name": "eth0"},
        )
        await iface.save(allow_upsert=True)
```

**Correct — reuse the local object:**

```python
async def generate(self, data: dict) -> None:
    for spec in sorted(data["device_specs"], key=lambda s: s["name"]):
        device = await self.client.create(
            kind="DcimDevice", data={"name": spec["name"]},
        )
        await device.save(allow_upsert=True)

        iface = await self.client.create(
            kind="DcimInterface",
            data={"device": device.id, "name": "eth0"},  # reuse
        )
        await iface.save(allow_upsert=True)
```

If the create-and-reference pair spans more code, pass the local
reference through `self.store`:

```python
self.store.set(key=spec["name"], node=device)
# ... later in another helper ...
parent = self.store.get(key=spec["name"])
```

### Common Mistakes

- "I want a fresh copy" — the local object IS the fresh copy. Server
  responses don't add fields the SDK didn't already populate.
- Treating `.get()` as a way to "confirm the save worked" — `.save()`
  raises on failure; if it returned, the save succeeded.
- Re-fetching to "refresh related fields" — pass relationship references
  by id from the local object instead.

### Source

- SDK: `infrahub_sdk/store.py:25-50` (NodeStoreBranch is the canonical
  in-process cache; never consulted by `.get()` / `.filters()`).
- SDK: `infrahub_sdk/client.py:849-919` (every `.filters()` /
  `.get()` is a full HTTP round-trip).
