---
title: Tracking System and Idempotent Behavior
impact: HIGH
tags: tracking, idempotent, delete_unused_nodes, allow_upsert, update_group_context, shared-objects
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

## The Tracking Group Is Per Target, Not Per Generator

The group's name is the generator definition's
identifier plus a hash of the **run parameters**. Since
the parameters differ per target, **two targets produce
two groups**, and each one's cleanup set is computed
only against its own previous membership.

That matters as soon as one object is reachable from
more than one target.

### An upsert claims ownership just as a create does

**Every `save()` adds the node to the current run's
group, including an upsert of a node that already
existed.** The call is unconditional: `save()` runs the
create-or-update, then adds the node to the group
context regardless of which branch it took.

This is the fact that makes a shared object dangerous,
and it is the opposite of the natural reading. An upsert
looks like idempotent housekeeping. It is a claim of
ownership.

```python
# Target A's run and target B's run both do this.
# Whichever runs last owns the container.
container = await self.client.create(
    kind="NetContainer", data={"name": "shared-trunk"},
)
await container.save(allow_upsert=True)   # claims it
```

### The failure is a refusal, not a changed output set

The obvious danger is a generator whose output *varies*
between runs. A shared object is worse, because the
generator's output does not vary at all:

- Target A's run creates the shared container. Target
  B's run nests a child under it. **Re-running A leaves
  both intact.** This is the case a developer tests, and
  it looks safe.
- Later, A's run takes a refusal path and stops writing
  the shared container. **The container is deleted**, and
  B's child is left with an empty parent relationship.

The second case is reachable by a refusal, a
de-provision or a re-route — none of which look like
"the generator's output set changed". And because the
relationship carries `on_delete: no-action`, the
sibling's child is **orphaned rather than deleted**:
nothing cascades, nothing errors, and the data is simply
wrong. That is the quieter of the two possible failures.

### The ownership test

> A generator may write an object only if that object
> belongs to the target the run is for. If two targets
> can both reach an object, the object belongs to
> neither.

Two ways to honour it:

1. **Create the shared object outside the generator** —
   in an object data file, or a separate one-off
   generator with its own single target.
2. **Opt out of tracking for that save:**

   ```python
   await container.save(allow_upsert=True, update_group_context=False)
   ```

   The node is written and **not** added to the run's
   group, so no run can reclaim it. Note this also means
   nothing cleans it up: that is the trade.

`update_group_context=False` is checked before anything
else, so it wins over the client's tracking mode.

### What cleanup actually deletes

Only members of *that one group* that are absent from
*this* run, and only when `delete_unused_nodes` is set:

```text
to_delete = previous_group.members - nodes_saved_this_run
```

A node that was never added to any group appears in
neither set and cannot be reclaimed — which is precisely
why the opt-out is safe for a genuinely shared object.

Reference:
[registration-config.md](registration-config.md),
[Infrahub Generator Docs](https://docs.infrahub.app)
