---
title: Accept File, Folder, or List of Paths
impact: HIGH
description: >-
  Accept any combination of a single CSV/TSV file, a directory (recursively
  scanned for *.csv / *.tsv), or a list of paths. Normalize to a flat file
  list with dedup + readable-only filter before profiling.
tags: inputs, normalization, files, directories
---

## Accept File, Folder, or List of Paths

Impact: HIGH

The skill accepts any of: a single CSV/TSV file, a
directory (recursively scanned for `*.csv` and
`*.tsv`), or a list of paths in any combination.
Normalize to a flat file list before profiling so
downstream logic doesn't branch on input shape.

### Why it matters

Real spreadsheet imports arrive in all three
shapes:

- `inventory.csv` — a single file the user just
  exported.
- `./imports/` — a directory the user dropped from
  another system, with mixed file types.
- `manufacturers.csv devices.csv interfaces.csv` —
  multiple files passed explicitly because the
  user wants a specific subset of a larger folder.

If the mapping logic has to handle each shape
separately, the code path multiplies and the
heuristics get applied inconsistently. Normalizing
upfront means every later step sees the same flat
list and the user gets predictable behavior
regardless of how they invoked the skill.

### What normalization does

1. **Expand directories.** For each directory in
   the input, recursively find every file matching
   `*.csv` or `*.tsv` (case-insensitive).
2. **Filter to readable files.** Drop entries the
   user can't actually read — broken symlinks,
   files with `.csv` extension but no read
   permission. Report what was dropped.
3. **De-duplicate.** If the same file shows up
   twice (e.g., a path in a folder that's also
   listed explicitly), include it once.
4. **Preserve user-supplied order** for paths
   given explicitly; sort alphabetically within
   each expanded directory.

### Reject non-CSV/TSV inputs

If an explicit path is `.json`, `.xlsx`, `.parquet`,
or anything else, fail with a clear message:

```text
Cannot import: 2 inputs are not CSV/TSV.

Rejected:
  - inventory.xlsx   (.xlsx is not supported; v1 covers CSV + TSV only)
  - data.json        (.json is not supported)

Consider one of:
  - Export the XLSX as CSV from your spreadsheet tool.
  - For JSON, see the future companion skill for non-CSV imports.

No files have been written.
```

This is the same fail-closed posture as the
unmapped-columns case in
[workflow-fail-closed-on-unmapped-columns.md](./workflow-fail-closed-on-unmapped-columns.md).
Better to surface the mismatch upfront than
process some files and silently drop others.

### CSV vs TSV detection

The extension is the primary signal. If both
extensions appear and the content disagrees with
the extension (a `.csv` actually uses tabs), prefer
the extension and warn the user — re-extension is
a one-line `mv` and avoids ambiguous heuristics on
mixed inputs.

### Common mistakes

- **Treating a directory like a single file.** A
  directory pointing at 10 CSVs is 10 imports,
  each with its own mapping draft. Don't collapse
  them.
- **Sorting before user-supplied order.** If the
  user passed `manufacturers.csv devices.csv` in
  that order, that's their preferred load-order
  hint — respect it (subject to schema
  dependencies overriding).
- **Following symlinks blindly.** Recursive scans
  should follow symlinks within the working tree
  but stop at the project boundary so the skill
  doesn't accidentally pick up unrelated CSVs from
  `~/Downloads/`.

Reference: [Infrahub Docs](https://docs.infrahub.app)
