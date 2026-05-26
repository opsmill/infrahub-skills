---
title: Don't Catch Broad Exceptions in generate()
impact: HIGH
tags: error-handling, tracking, exception, silent-failure
---

## Don't Catch Broad Exceptions in generate()

Impact: HIGH

Inside `generate()`, do not catch `Exception` or use a bare `except:`
without re-raising. Swallowed exceptions corrupt the tracking system's
view of what was committed.

### Why It Matters

The tracking system commits the in-memory `related_node_ids` list to the
`CoreGeneratorGroup` only when `generate()` completes without raising
(`infrahub_sdk/client.py:1755-1764` — `__aexit__` only calls
`group_context.update_group()` when `exc_type is None`).

If you catch an exception mid-loop and let `generate()` "succeed":

- The tracking context exits cleanly.
- The group is updated with whatever objects were in
  `related_node_ids` at exit time.
- Any partial state from before the swallowed exception becomes
  permanent.
- On the next run, `delete_unused_nodes=True` operates on this partial
  set as the new ground truth.

Result: silent state corruption that's invisible until production
re-runs reveal missing objects.

### The Rule

If you must handle a specific exception (e.g., a known-recoverable SDK
error), catch it narrowly and re-raise after cleanup. Never use:

```python
try:
    ...
except:           # bare except — bad
    ...

try:
    ...
except Exception: # broad — bad
    pass
```

Use specific exception types and re-raise if the generator can't
honestly recover:

```python
try:
    await obj.save(allow_upsert=True)
except SomeSpecificSDKError as exc:
    logger.warning("transient: %s", exc)
    raise
```

### Example

**Incorrect — swallows partial failure:**

```python
async def generate(self, data: dict) -> None:
    for element in sorted(data["elements"], key=lambda e: e["role"]):
        try:
            obj = await self.client.create(kind="Foo", data={...})
            await obj.save(allow_upsert=True)
        except Exception:
            continue  # tracking group exits "clean" with partial state
```

**Correct — narrow handling that re-raises:**

```python
async def generate(self, data: dict) -> None:
    for element in sorted(data["elements"], key=lambda e: e["role"]):
        obj = await self.client.create(kind="Foo", data={...})
        await obj.save(allow_upsert=True)
        # Let any exception propagate. The framework retries; the
        # tracking system stays consistent.
```

### Common Mistakes

- "Log and continue" patterns — they convert hard failures into invisible
  corruption.
- Catching `Exception` to "make the generator more robust" — the framework
  has its own retry and observability layers; you defeat them by catching.
- Catching specific exceptions but not re-raising — same failure mode as
  bare except for any case where the partial state isn't safe.

### Source

- SDK: `infrahub_sdk/client.py:1755-1764` (group context only commits on
  clean exit).
- Backend: `infrahub/generators/tasks.py:75-96` (re-raises on failure;
  swallowed exceptions break this contract).
