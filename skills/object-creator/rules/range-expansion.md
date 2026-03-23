---
title: Interface Range Expansion
impact: MEDIUM
tags: range, expansion, interfaces, sequential
---

## Interface Range Expansion

Impact: MEDIUM

For interfaces with sequential names, use range syntax
with `expand_range: true` to avoid repetitive entries.

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

- `expand_range: true` goes under `parameters`, not on individual data items
- All expanded interfaces share the same attribute values (role, status, etc.)
- Range uses inclusive bounds: `[1-4]` means 1, 2, 3, and 4

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
