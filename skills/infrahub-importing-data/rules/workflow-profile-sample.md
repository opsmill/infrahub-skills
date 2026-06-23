---
title: Profile Each Input File Before Mapping
impact: MEDIUM
description: >-
  Read the header plus a sample (default 20 rows, or more if needed for
  dropdown / range detection) of every input file before drafting the
  mapping. Profile what's there: per-column distinct value counts, sample
  values, and any obvious sequence patterns.
tags: workflow, profile, sample, detection
---

## Profile Each Input File Before Mapping

Impact: MEDIUM

Before mapping (step 4 in the SKILL.md workflow),
read each file's header and a representative sample
of rows. Profiling produces the column-level facts
the mapping ladder consumes: distinct-value counts
(does this column look like a dropdown?), sample
values (does the shape match a reference HFID?),
and sequence patterns (is this an interface-shaped
range?).

### Why it matters

Without profiling, the mapping step asks the schema
"do you have an attribute named X?" without
knowing whether X's *values* fit any reasonable
type. The detection rules for dropdown
([mapping-dropdown-label-to-name.md](./mapping-dropdown-label-to-name.md)),
reference
([mapping-reference-and-hfid.md](./mapping-reference-and-hfid.md)),
range
([range-detection.md](./range-detection.md)), and
denormalization
([decomposition-denormalized-csv.md](./decomposition-denormalized-csv.md))
all rely on summarized column-level facts that
profiling provides.

### Sample size

Default: header + 20 data rows.

Increase the sample when:

- **Dropdown detection.** Need at least N rows
  where N covers the schema's choice count plus
  reasonable variation. For a 10-choice Dropdown,
  read ≥ 100 rows so the sample is likely to
  include every choice.
- **Range detection.** Read enough rows to see at
  least one complete parent group. For interfaces
  on a 48-port device, that's ≥ 48 rows.
- **Denormalization detection.** Read enough rows
  to detect the group-key shift. The detection
  needs ≥ 2 distinct group-key values; in
  practice read until you've seen 3+ distinct
  values for the candidate parent key.

If the file is small (< 200 rows), read everything.
Memory cost is negligible at that scale.

### What to record per column

| Fact | Why it matters |
| ---- | -------------- |
| Distinct value count | Low count (≤ 10) over a large sample suggests dropdown candidate |
| Sample values (first 5 distinct) | Disambiguates "looks like enum" from "looks like free-form text" |
| Min / max length | Distinguishes ID-shaped columns from prose columns |
| Numeric-only fraction | Suggests Number attribute (with coercion via [mapping-value-coercion.md](./mapping-value-coercion.md)) |
| Date-pattern match fraction | Suggests DateTime attribute |
| Sequence pattern (`<prefix><N>`) | Range candidate per [range-detection.md](./range-detection.md) |
| Blank cell fraction | Drives the [mapping-empty-and-null.md](./mapping-empty-and-null.md) decision |
| Per-group constancy | Denormalization signal — see [decomposition-denormalized-csv.md](./decomposition-denormalized-csv.md) |

### When the file has no header

A CSV without a header row is rare but happens (raw
exports). Profile the first row and ask the user in
the interview whether it's data or header. Never
infer header status from value-shape heuristics
alone — the wrong call corrupts every column
binding.

### Use the profile to write the plan

Echo a per-file profile summary into the
confirm-and-lock plan (step 7) so the user can see
what the mapping is based on:

```text
inventory.csv (260 rows × 8 columns):
  name              : 260 distinct, len 5-12, free-form        → Text attribute
  role              : 4 distinct (spine, leaf, edge, mgmt)    → Dropdown candidate
  status            : 3 distinct (Active, Maintenance, ...)   → Dropdown (labels)
  manufacturer_name : 5 distinct, low cardinality            → reference candidate
  port_count        : 100% numeric                            → Number attribute
  commissioned_at   : 100% YYYY-MM-DD pattern                → DateTime attribute
  ...
```

### Common mistakes

- **Reading only 5 rows for a large file.** The
  sample is too small for dropdown/range/
  denormalization detection to fire correctly.
- **Skipping per-group constancy analysis.** A
  column that varies within rows but is constant
  within parent groups is the strongest signal of
  a denormalized parent column. Without per-group
  analysis the detector misses denormalization.
- **Profiling once and reusing the result across
  re-runs.** Inputs change; profile every run.

Reference: [Infrahub Docs](https://docs.infrahub.app)
