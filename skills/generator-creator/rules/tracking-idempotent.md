---
title: Tracking System and Idempotent Behavior
impact: HIGH
tags: tracking, idempotent, delete_unused_nodes, allow_upsert
---

## Tracking System and Idempotent Behavior

Impact: HIGH

The `run()` method wraps your `generate()` call in a
tracking context with `delete_unused_nodes=True`.

### How Tracking Works

1. Objects created/updated during `generate()` are tracked
2. Objects from a previous run that are NOT created/updated
   in the current run are automatically deleted
3. This ensures idempotent behavior: re-running a generator
   cleans up stale objects

### Why `allow_upsert=True` Is Essential

**Incorrect -- without upsert (fails on re-run):**

```python
device = await self.client.create(
    kind="DcimDevice",
    data={"name": "spine-01"},
)
await device.save()  # Fails if spine-01 already exists!
```

**Correct -- idempotent with upsert:**

```python
device = await self.client.create(
    kind="DcimDevice",
    data={"name": "spine-01"},
)
await device.save(allow_upsert=True)  # Creates or updates
```

### Implications

- If you remove an element from your design, re-running
  the generator will automatically delete the
  corresponding objects
- All objects created within a single `generate()` run
  are part of the same tracking group
- Objects not touched in the current run are considered
  stale and removed

Reference:
[Infrahub Generator Docs](https://docs.infrahub.app)
