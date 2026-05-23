---
title: Use String Literals for kind= Arguments
impact: MEDIUM
tags: static-analysis, kind, literal, cascade
---

## Use String Literals for kind= Arguments

Impact: MEDIUM

Every `kind=` argument to `self.client.create(...)`,
`self.client.get(...)`, and `self.client.filters(...)` must be a string
literal — not a variable, attribute access, or computed expression.

### Why It Matters

Dynamic kinds defeat static analysis. Graders (including the cascade
one-layer check) skip non-literal kinds because they can't be
determined without runtime evaluation. A model that uses
`kind=design.element_kind` to "be flexible" bypasses every static
check the skill enforces.

More importantly, dynamic kinds almost always reflect a confused design:

- If the kind genuinely varies, the generator is doing multiple layers
  in one place — split it (see
  [cascade-one-layer.md](./cascade-one-layer.md)).
- If the kind is constant but indirected through a variable, the
  variable name often hides what's being created from anyone reading the
  code (and from the grader).
- If the kind is loaded from configuration, you've introduced runtime
  schema dependency in code that should be declarative.

A literal `kind="DcimDevice"` is clear to readers, clear to graders,
and clear to schema-drift tooling.

### The Rule

Every `kind=` argument is an inline string literal:

```python
await self.client.create(kind="DcimDevice", data={...})  # ✓
await self.client.get(kind="DcimDevice", id=device_id)   # ✓
```

Not:

```python
KIND = "DcimDevice"
await self.client.create(kind=KIND, data={...})  # ✗ indirection
await self.client.create(kind=design.kind, data={...})  # ✗ runtime
```

### Example

**Incorrect — dynamic kind hides multi-layer creation:**

```python
async def generate(self, data: dict) -> None:
    for element in sorted(data["elements"], key=lambda e: e["kind"]):
        obj = await self.client.create(
            kind=element["kind"],   # hidden from static analysis
            data=element["fields"],
        )
        await obj.save(allow_upsert=True)
```

**Correct — explicit kinds per branch:**

```python
async def generate(self, data: dict) -> None:
    for element in sorted(data["elements"], key=lambda e: e["role"]):
        if element["role"] == "spine":
            obj = await self.client.create(
                kind="DcimDevice", data={...},
            )
        elif element["role"] == "edge":
            obj = await self.client.create(
                kind="DcimEdgeDevice", data={...},
            )
        else:
            raise ValueError(f"unknown role: {element['role']}")
        await obj.save(allow_upsert=True)
```

If branches multiply, that's the signal to split into multiple
generators (one per kind) and let the registration layer route work.

### Common Mistakes

- Using a constant at module scope (`KIND = "DcimDevice"`) — DRY-style
  but defeats the grader and adds indirection for no real saving.
- Computing kind from a schema property (`kind=schema_node.kind`) — the
  schema is known at write time; bake the kind in.
- Treating the rule as cosmetic — it's the leading indicator for the
  multi-layer-generator antipattern.

### Source

- This rule closes a known evasion path on the `cascade-one-layer`
  check, which skips non-literal kinds by design (can't statically
  determine intent).
