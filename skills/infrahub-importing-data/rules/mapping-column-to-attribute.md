---
title: Map Columns to Attributes by Heuristic Order
impact: CRITICAL
description: >-
  Apply the heuristic ladder — exact name → snake_case round-trip →
  display-label fuzzy → unit-strip → unmapped — and stop at the first
  match. Anything past unit-strip routes to the interview; never invent
  a binding silently.
tags: mapping, columns, attributes, heuristics, fuzzy-match
---

## Map Columns to Attributes by Heuristic Order

Impact: CRITICAL

Apply the heuristic ladder in
[../reference.md](../reference.md) and stop at the
first match: exact name → snake_case round-trip →
display-label fuzzy → unit-strip → unmapped. Anything
past unit-strip routes to the interview; the skill
never invents a binding silently.

### Why it matters

CSV headers come in inconsistent shapes — "Serial
Number", "serial_number", "S/N", "Memory (GB)".
Most map to a schema attribute trivially; a few
need help. The risk is that a "close enough" guess
binds the wrong column to the wrong attribute and
the data lands somewhere it doesn't belong. The
heuristic order is conservative: each step is more
expensive (and more ambiguous) than the last, and
the user is the tiebreaker beyond a point the
skill can defend.

### The heuristic ladder

1. **Exact name match (case-sensitive).** `name` →
   `name`. Trust this without confirming.
2. **snake_case round-trip.** Lowercase, replace
   non-alphanumeric runs with `_`, strip
   leading/trailing `_`. `Serial Number` →
   `serial_number`; `S/N` → `s_n`. Match against
   attribute names.
3. **Display-label fuzzy.** Some schema attributes
   carry a human `label` (`label: "Rack U
   Position"` for attribute `rack_u_position`).
   Match the CSV column (case-insensitive,
   whitespace-collapsed) against the schema label.
4. **Unit-strip.** Drop parenthesized suffixes
   like `(GB)`, `(MHz)`, `(W)` from the column
   name and re-run steps 1–3.
5. **Unmapped.** Anything that reaches this step
   is a candidate for the fail-closed gate
   ([workflow-fail-closed-on-unmapped-columns.md](./workflow-fail-closed-on-unmapped-columns.md)).
   Surface it in the interview; the only way it
   doesn't block emission is if the user
   deliberately marks "skip."

### What counts as ambiguous (and defers)

Even within the first three steps, some matches
are ambiguous enough to deserve a confirmation:

- A column name that matches multiple attributes
  by fuzzy rules (e.g., `address` matches both
  `address` and `address_line1`).
- A snake_case round-trip that produces a name
  that's similar to but not identical to an
  attribute (`u_pos` → would-be `u_pos` doesn't
  match `rack_u_position`).
- Unit-strip produces a match but the original
  carries a unit the attribute doesn't carry (the
  attribute might already be in different units
  than the CSV).

When in doubt, defer to the interview. The cost of
one extra question is much smaller than the cost
of silently mapping the wrong column.

### Incorrect — silent fuzzy guess

```text
Column "Memory" → attribute "memory_gb" (close enough)
Column "Memory (TB)" → attribute "memory_gb" (after unit-strip)
```

Both bindings sneak past a casual review. The unit
mismatch in the second line means values get loaded
in the wrong unit — every value is 1000× wrong.

### Correct — defer the unit-stripped match

```text
Column "Memory (GB)" → snake_case → "memory_gb"
  → exact match → bind to attribute memory_gb.
Column "Memory (TB)" → snake_case → "memory_tb"
  → no exact match. Unit-strip → "memory".
  → no exact match.
  → No safe binding. Surface in interview:

    Column "Memory (TB)":
      Schema has "memory_gb" (Number, GB).
      The CSV column units don't match.
      a) Convert TB→GB on the fly and bind to memory_gb
      b) Skip the column (no schema attribute exists)
      c) Add a new attribute (escalate to managing-schemas)
```

### Common mistakes

- **Lowercasing both sides and calling it a match.**
  Snake_case round-trip is more deliberate; do
  that.
- **Trusting unit-strip silently.** If the unit
  differs (TB vs GB), the values need conversion
  the skill is not authorized to perform on its
  own.
- **Skipping straight to the interview without
  trying the ladder.** Most columns map by step 1
  or 2; the interview should only carry the
  genuinely ambiguous cases.

Reference: [Infrahub Docs](https://docs.infrahub.app)
