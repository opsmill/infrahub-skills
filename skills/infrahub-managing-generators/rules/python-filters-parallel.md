---
title: Pass parallel=True to client.filters() in generate()
impact: MEDIUM
tags: performance, pagination, parallel, N+1
---

## Pass parallel=True to client.filters() in generate()

Impact: MEDIUM

When calling `self.client.filters(...)` inside `generate()`, always pass
`parallel=True`. The SDK's filter pagination is sequential by default,
which adds one round-trip per page of 50.

### Why It Matters

`self.client.filters(...)` auto-paginates internally
(`infrahub_sdk/client.py:849-919`, `pagination_size=50`). With the
default `parallel=False`, pages are fetched one after another — for a
500-item result that's 10 sequential round-trips, each 0.5-1s.

Setting `parallel=True` issues all page fetches concurrently. For
result sets larger than 50 (which is most real-world generator inputs),
the speedup is roughly proportional to the page count.

The cost of the flag is zero when the result fits in one page —
there's nothing to parallelize, so no extra overhead. Safe to apply
universally.

### The Rule

Every `self.client.filters(...)` call inside `generate()` (or anywhere
in the generator file's helpers) must pass `parallel=True`.

### Example

**Slow — sequential pagination:**

```python
devices = await self.client.filters(
    kind="DcimDevice",
    role__value="spine",
)
```

**Fast — concurrent pagination:**

```python
devices = await self.client.filters(
    kind="DcimDevice",
    role__value="spine",
    parallel=True,
)
```

### Common Mistakes

- Worrying about `parallel=True` "for small queries" — the SDK only
  parallelizes when there's more than one page to fetch. There's no
  downside for tiny result sets.
- Using `client.all(kind=...)` for a "give me everything" fetch — `.all()`
  also paginates and is the same shape; pass `parallel=True` there too.
- Iterating `.filters()` results inside a per-item `.create()` loop —
  that's an N+1 pattern; fetch upfront, key by id, then loop the local
  list.

### Source

- SDK: `infrahub_sdk/client.py:849-919` (`pagination_size=50`,
  `parallel=False` default).
