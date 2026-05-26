---
title: Stable Iteration in Create Loops
impact: HIGH
tags: deterministic, sorting, idempotent, ordering
---

## Stable Iteration in Create Loops

Impact: HIGH

When iterating a collection from a GraphQL response to create child objects,
wrap the iterable in `sorted(...)` with an explicit key. Re-runs against the
same upstream data should produce byte-identical downstream output.

### Why It Matters

GraphQL responses preserve list order from the server, but that order can
shift when underlying objects are added, deleted, or reindexed. If your
create-loop derives names or sequence numbers from incoming order, those
derived values drift across runs.

The tracking system (`delete_unused_nodes=True`) treats a drifted name as
"new object, old object missing" — it creates the new one and deletes the
old. Result: spurious churn that looks like real change in diffs and audit
logs.

Stable sorting eliminates the variable. Re-running the generator against the
same upstream data always produces the same downstream output.

### The Rule

Any `for` loop inside `generate()` that contains a `.create(...)` call must
iterate over `sorted(...)` (or `range(...)`, which is already deterministic).
Sort by a stable, semantically meaningful key — usually `id`, `name`, or a
domain-specific identifier like `role`.

### Example

**Incorrect — order depends on the GraphQL response:**

```python
for element in design["elements"]:
    device = await self.client.create(kind="DcimDevice", data={...})
    await device.save(allow_upsert=True)
```

**Correct — sorted by a stable key:**

```python
for element in sorted(design["elements"], key=lambda e: e["role"]):
    device = await self.client.create(kind="DcimDevice", data={...})
    await device.save(allow_upsert=True)
```

**Also correct — range-based iteration is already deterministic:**

```python
for i in range(1, quantity + 1):
    device = await self.client.create(
        kind="DcimDevice",
        data={"name": f"{topology}-{role}-{i:02d}"},
    )
    await device.save(allow_upsert=True)
```

### Common Mistakes

- Sorting by UUID `id` — produces stable but semantically meaningless
  ordering. Prefer a domain key like `name` or `role`.
- Forgetting `key=` and letting Python compare dicts directly — raises
  `TypeError`.
- Iterating `dict.items()` and assuming insertion order is good enough — it
  isn't when the dict came from a GraphQL response that may reorder between
  runs.
- Adding sorting only to the outer loop while the inner loop creates from an
  unsorted nested list — the rule applies to *every* create-loop, not just
  the top one.
