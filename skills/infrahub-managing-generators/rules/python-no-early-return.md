---
title: Don't Return Early After Creating or Saving
impact: HIGH
tags: error-handling, tracking, early-return, partial-commit
---

## Don't Return Early After Creating or Saving

Impact: HIGH

Inside `generate()`, `return` may appear only *before* the first
`.create()` or `.save()` call. An early return after partial work leaves
the tracking group in an inconsistent state — the same failure mode as a
swallowed exception, but more tempting to write.

### Why It Matters

The tracking system finalizes the `CoreGeneratorGroup` only when
`generate()` exits cleanly. An early `return` is a clean exit by Python
semantics — but it commits the partial set of `related_node_ids` from
that point as the canonical group membership.

On the next run, `delete_unused_nodes=True` treats that partial set as
ground truth. Any object the generator *would have created* on the path
after the return is now orphaned: it was never tracked, and the
generator no longer re-creates it.

### The Rule

If you need to short-circuit on a precondition (empty input, feature
flag off, etc.), do it as a guard at the *top* of `generate()`, before
any mutation. Once you've called `.create()` or `.save()`, you commit
to running through to the end (or letting an exception propagate).

### Example

**Incorrect — early return after partial work:**

```python
async def generate(self, data: dict) -> None:
    for element in sorted(data["elements"], key=lambda e: e["role"]):
        if element.get("disabled"):
            return  # partial commit — the rest never happens
        obj = await self.client.create(kind="Foo", data={...})
        await obj.save(allow_upsert=True)
```

**Also incorrect — early return after one branch:**

```python
async def generate(self, data: dict) -> None:
    obj = await self.client.create(kind="Foo", data={...})
    await obj.save(allow_upsert=True)
    if data.get("skip_extras"):
        return  # partial commit; extras_obj never created and never tracked
    extras = await self.client.create(kind="FooExtras", data={...})
    await extras.save(allow_upsert=True)
```

**Correct — short-circuit guards run before any mutation:**

```python
async def generate(self, data: dict) -> None:
    elements = data["elements"]
    if not elements:
        return  # safe — no mutation has happened yet

    for element in sorted(elements, key=lambda e: e["role"]):
        # ... raise on per-element disabled flag rather than return
        if element.get("disabled"):
            raise ValueError(
                f"disabled element {element['name']} encountered mid-run"
            )
        obj = await self.client.create(kind="Foo", data={...})
        await obj.save(allow_upsert=True)
```

### Common Mistakes

- Using `return` as "skip the rest of this iteration" — that's `continue`
  inside a loop, not `return` from the function.
- Returning early to "save time on no-op runs" — the tracking system
  needs to see the full intended set every run to be correct.
- Confusing this with the cascade checksum-guard `continue` pattern —
  `continue` inside a sorted loop is fine; `return` from the function
  body after creates is not.

### Source

- SDK: `infrahub_sdk/client.py:1755-1764` (clean-exit commit semantics
  apply equally to `return` and falling off the end of the function).
