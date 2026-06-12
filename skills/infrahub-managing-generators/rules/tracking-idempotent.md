---
title: Tracking System and Idempotent Behavior
impact: HIGH
tags: tracking, idempotent, delete_unused_nodes, allow_upsert
---

## Tracking System and Idempotent Behavior

Impact: HIGH

`run()` wraps `generate()` in a tracking context
with `delete_unused_nodes=True`, so the generator's
output is treated as the desired state for its
target.

### Why it matters

Generators are stateful: a re-run cleans up objects
from the previous run that weren't recreated this
time, which is what lets the generator "drive" the
target instead of just accumulating data. That only
works if every `save()` uses `allow_upsert=True` —
without upsert the second run errors on the first
existing object and aborts, leaving the tracking
group half-updated. The flip side is that a buggy
generator (one that skips objects it shouldn't, or
narrows its target too far) can delete real data on
the next run; the tracking group is the blast
radius, so keeping `generate()` deterministic and
defensive about empty input matters more here than
in checks or transforms.

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
