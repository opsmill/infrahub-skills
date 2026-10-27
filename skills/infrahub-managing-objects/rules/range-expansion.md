---
title: Interface Range Expansion
impact: MEDIUM
tags: range, expansion, interfaces, sequential
---

## Interface Range Expansion

Impact: MEDIUM

Sequential interface names use bracket-range syntax
(`Ethernet1/[1-4]`) together with `expand_range:
true` set under `parameters` on the relationship
block.

### Why it matters

`expand_range` is a loader directive that applies to
a whole `data:` list — it tells the loader to fan
out each ranged entry into individual items before
upsert. Placing it on an individual data item
silently has no effect: the loader looks for it on
`parameters`, doesn't find it, and treats
`Ethernet1/[1-4]` as a literal interface name with
brackets in it. The first run creates one strangely
named interface; the user only notices when the
expected 4-port range never appears.

**Incorrect -- expand_range on individual items:**

```yaml
interfaces:
  kind: InterfacePhysical
  data:
    - name: Ethernet1/[1-4]
      expand_range: true              # Wrong! Goes on parameters, not data items
      role: customer
```

**Correct -- expand_range in parameters block:**

```yaml
interfaces:
  kind: InterfacePhysical
  parameters:
    expand_range: true                # Set on the relationship block
  data:
    - name: Ethernet1/[1-4]           # Expands to 1/1 through 1/4
      role: customer
      status: active
```

### Range Syntax

| Pattern | Expands To |
| ------- | ---------- |
| `Ethernet1/[1-4]` | Ethernet1/1 through Ethernet1/4 |
| `et-0/0/[0-31]` | et-0/0/0 through et-0/0/31 |
| `GigE[1-48]` | GigE1 through GigE48 |

### Key Rules

- `expand_range: true` belongs under `parameters`,
  not on individual data items
- Expanded interfaces share the same attribute
  values (role, status, etc.)
- Range bounds are inclusive — `[1-4]` covers 1, 2,
  3, and 4

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
