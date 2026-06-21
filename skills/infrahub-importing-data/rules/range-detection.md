---
title: Collapse Interface-Shaped Sequences Into Range Syntax
impact: MEDIUM
description: >-
  When a CSV column's values form a contiguous interface-shaped sequence
  within a single parent and sibling columns are identical across the
  range (≥4 rows), emit a bracket-range entry plus
  parameters.expand_range: true on the relationship block.
tags: range, interfaces, sequences, expand_range, detection
---

## Collapse Interface-Shaped Sequences Into Range Syntax

Impact: MEDIUM

When a CSV column's values form a contiguous
interface-shaped sequence (e.g., `eth0, eth1, …,
eth47`) within a single parent and the sibling
columns are identical across the range, emit a
collapsed bracket-range entry plus
`parameters.expand_range: true` on the relationship
block.

The emission shape is fully specified in
[../../infrahub-managing-objects/rules/range-expansion.md](../../infrahub-managing-objects/rules/range-expansion.md);
this rule covers the **detection** that decides
whether to collapse in the first place.

### Why it matters

48-port leaves and 32-port spines produce CSVs
with 48 (or 32, or N) near-identical rows. Emitted
literally, the YAML is hundreds of lines of
repetition that the user has to review by hand for
typos. The loader's `expand_range` directive
exists for exactly this case — collapse to one
entry, fan out at load time. Skipping the
collapse means:

- Every row gets reviewed individually for a
  difference the human's eye can't catch.
- The emitted file is 10× larger than it needs to
  be.
- A typo in row 23 only surfaces at load.

The opposite mistake is over-collapsing — treating
sequence-looking values as a range when one row
genuinely differs from the others. The range
expansion at load time produces N identical items;
any per-item difference vanishes silently.

### Detection criteria

Collapse only when **all** of these hold within a
single parent's row group:

1. **Contiguous numeric suffix.** The names share
   a prefix and the numeric suffixes form a
   contiguous, gap-free sequence
   (`eth0..eth47`, not `eth0,eth1,eth5`).
2. **Identical sibling columns.** Every other
   column for the same parent is identical across
   the range. If `role`, `status`, or any other
   attribute varies even once, the range cannot
   collapse.
3. **At least 4 rows.** Collapsing 2 or 3 rows
   saves little and obscures the input shape;
   leave short sequences as individual entries.

If any criterion fails, split the range:

```text
Input: eth0(server)..eth15(server), eth16(uplink), eth17(server)..eth47(server)

Detection: contiguous numeric suffix, but eth16
sibling column differs. Cannot collapse into a
single range.

Emission options:
  a) eth[0-15] (server) + eth16 (uplink) + eth[17-47] (server)
     — three entries
  b) Emit 48 rows individually
     — loses the size benefit but preserves shape
```

Confirm in the interview if the partial collapse
is non-obvious.

### Range syntax examples

| Input names | Collapsed |
| ----------- | --------- |
| `eth0..eth47` | `eth[0-47]` |
| `Ethernet1/1..Ethernet1/48` | `Ethernet1/[1-48]` |
| `et-0/0/0..et-0/0/31` | `et-0/0/[0-31]` |
| `GigE1..GigE48` | `GigE[1-48]` |

The bracketed range is **inclusive on both ends**
— `[1-4]` covers 1, 2, 3, 4.

### Emission shape (cross-reference)

Always put `expand_range: true` under
`parameters:`, never on the data item. See
[../../infrahub-managing-objects/rules/range-expansion.md](../../infrahub-managing-objects/rules/range-expansion.md)
for the full rationale; the short version is that
`expand_range` is a loader directive applied to the
whole `data:` list — placing it on an item is a
no-op and silently creates one literal interface
named `eth[0-47]`.

```yaml
interfaces:
  kind: InterfacePhysical
  parameters:
    expand_range: true
  data:
    - name: eth[0-47]
      role: server
      status: active
```

### Cross-parent ranges don't collapse

If `spine-01` has `eth0..eth47` and `spine-02` has
`eth0..eth47`, the ranges collapse **per parent**,
not across parents — each parent gets its own
collapsed entry inside its own row in the parent's
`data:` list.

### Common mistakes

- **Collapsing when sibling columns vary.** The
  resulting fan-out is silently wrong; every port
  ends up with the same role/status.
- **Aggressive collapsing on short sequences (2–3
  ports).** Hard to read at review time; the
  benefit isn't worth the obfuscation.
- **Putting `expand_range: true` on the data
  item.** No-op; emits one literal-bracket
  interface.
- **Trying to collapse non-numeric suffixes.**
  `eth-mgmt0, eth-mgmt1` works; `eth-mgmt0,
  eth-data0` doesn't (different prefixes).

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
