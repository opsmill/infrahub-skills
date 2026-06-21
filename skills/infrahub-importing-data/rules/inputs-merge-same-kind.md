---
title: Merge Multiple Inputs of the Same Kind Into One File
impact: MEDIUM
description: >-
  When two or more input CSVs produce rows of the same target kind
  (e.g., manufacturers-na.csv + manufacturers-eu.csv → OrganizationManufacturer),
  merge them into a single NN-prefixed output file. Each kind is produced
  by exactly one file.
tags: inputs, merge, dedup, load-order
---

## Merge Multiple Inputs of the Same Kind Into One File

Impact: MEDIUM

A single import session can take multiple input CSVs
that all map to the same target kind — typically a
geographic or business-unit split like
`manufacturers-na.csv` + `manufacturers-eu.csv`, or a
multi-export from the same source system. The
emission must merge these into one numbered output
file per kind, not one output per input.

### Why it matters

Emitting two `NN_manufacturers.yml` files is
self-defeating:

1. **Load-order ambiguity.** Two files with the
   same kind compete for the same numeric prefix
   slot. The loader's behavior across same-prefix
   files is filesystem-dependent and not
   contractually deterministic.
2. **Duplicate HFID collisions.** If both files
   emit a row for `Cisco`, the second insert
   collides with the first and aborts the batch.
3. **Reviewer confusion.** A reader of the output
   has to mentally union two files to know what
   the import produced. One file per kind is the
   contract.

The `check_load_order_numbering` grader already
enforces "each kind is produced by exactly one
file." This rule is the consumer-facing statement
of that contract.

### Merge rules

1. **Group inputs by target kind.** After mapping is
   locked, partition the input rows by which kind
   they produce. Some inputs may contribute to
   multiple kinds (a denormalized sheet — see
   [decomposition-denormalized-csv.md](./decomposition-denormalized-csv.md));
   handle each kind separately.
2. **Concatenate rows under one `spec.data:` list.**
   Preserve user-supplied input order: rows from
   the first input listed come first.
3. **Dedupe by HFID.** If two inputs produce a row
   with the same HFID, the first occurrence wins
   and the duplicate is surfaced in the interview:

   ```text
   Duplicate row in OrganizationManufacturer:
     name = "Cisco" appears in both
       manufacturers-na.csv (row 4)
       manufacturers-eu.csv (row 12)

   Pick:
     a) Use the NA value (description = "Network vendor (NA)")
     b) Use the EU value (description = "Network vendor (EU)")
     c) Inspect both — they differ on more than name; this may be two distinct objects
   ```
4. **Emit one numbered file** named after the kind,
   not after any single input.

### Correct — merged emission

Inputs: `manufacturers-na.csv`, `manufacturers-eu.csv`

```text
output_dir/
  01_manufacturers.yml      # rows from both inputs, deduped by HFID
  02_devices.yml            # references the merged manufacturers
```

### Incorrect — per-input emission

```text
output_dir/
  01_manufacturers-na.yml   # WRONG — two files for the same kind
  01_manufacturers-eu.yml   # WRONG — duplicate prefix, undefined load order
  02_devices.yml
```

### When the inputs disagree on attribute values

If `manufacturers-na.csv` says `Cisco.country = US`
and `manufacturers-eu.csv` says
`Cisco.country = IE` for the same HFID, the merge
**must surface the conflict in the interview** —
silently picking one side is the wrong failure
mode. The interview shows the conflicting cells
side by side and asks for a resolution.

### When merge is the wrong call

If two inputs really represent distinct kinds that
happen to have similar columns — e.g., `vendors.csv`
should map to `OrganizationVendor` but
`manufacturers.csv` maps to
`OrganizationManufacturer` — the mapping step
should route them to different kinds. The merge
rule applies only after each input has been
assigned a target kind.

### Common mistakes

- **Concatenating without dedup.** Two rows with
  the same HFID load with the second insert
  aborting the batch.
- **Renaming the output to mention both inputs**
  (`01_manufacturers_na_eu.yml`). The filename
  signals the kind, not the inputs. Provenance
  comments — see
  [outputs-provenance-comment.md](./outputs-provenance-comment.md)
  — name the inputs.
- **Treating different schemas as a merge
  problem.** Different target kinds → different
  files; same target kind → merged file.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
