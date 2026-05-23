---
title: Validate Upstream Counts Before Creating
impact: CRITICAL
tags: validation, upstream, idempotent, partial-data
---

## Validate Upstream Counts Before Creating

Impact: CRITICAL

Before creating any object in `generate()`, validate that the GraphQL response
contains the expected number of items. A partial GraphQL response — for
example, when a design element wasn't fully populated, or a peer's
relationship returned fewer edges than expected — will otherwise silently
produce a partial fabric.

### Why It Matters

The tracking system runs every `generate()` call inside a
`delete_unused_nodes=True` context. Objects created on a previous run that
are NOT touched in the current run are treated as stale and deleted.

If your upstream data is incomplete and you skip validation:

1. `generate()` runs against partial data.
2. Only some children get created this run.
3. The tracking system *deletes* the previously-correct children that aren't
   in this run's data — they look stale.
4. You silently end up with a partial fabric that looks intentional.

Loud failure beats silent corruption.

### The Rule

At the top of `generate()`, before any `await self.client.create(...)` call,
compare the count of items received against the count the design says you
should have. Raise (or otherwise abort) on mismatch.

The count check itself is what matters; the exact expression can vary
(`len(elements) != expected`, `assert len(elements) == expected`,
`if not elements:`). What matters is that *no `.create(...)` runs before the
check passes*.

### Example

**Incorrect — creates objects from whatever data arrived:**

```python
async def generate(self, data: dict) -> None:
    topology = data["TopologyDataCenter"]["edges"][0]["node"]
    design = topology["design"]["node"]
    elements = design["elements"]["edges"]

    for element in elements:
        device = await self.client.create(
            kind="DcimDevice",
            data={...},
        )
        await device.save(allow_upsert=True)
```

**Correct — validates count before creating:**

```python
async def generate(self, data: dict) -> None:
    topology = data["TopologyDataCenter"]["edges"][0]["node"]
    design = topology["design"]["node"]
    expected = design["expected_element_count"]["value"]
    elements = design["elements"]["edges"]

    if len(elements) != expected:
        raise ValueError(
            f"Incomplete upstream data: expected {expected} design "
            f"elements, got {len(elements)}"
        )

    for element in sorted(elements, key=lambda e: e["node"]["role"]["value"]):
        device = await self.client.create(
            kind="DcimDevice",
            data={...},
        )
        await device.save(allow_upsert=True)
```

### Common Mistakes

- Validating *after* creating some objects — the tracking context has already
  begun, you're past the safe point.
- Checking `if elements:` (truthy) instead of comparing to the expected
  count — non-empty doesn't mean complete.
- Logging a warning instead of raising — the run continues and corrupts state.
- Skipping validation because the data "always looks fine in dev" — the
  failure mode is rare-but-silent, exactly the class of bug that ships.
