---
title: Detect and Handle CSV Dialect Quirks
impact: HIGH
description: >-
  Detect delimiter (`,` vs `;` vs `\t`), encoding (UTF-8, latin-1,
  windows-1252), BOM presence, and line endings before parsing. Use the
  Python csv.Sniffer-style approach on the first ~4KB; fail closed when
  the dialect can't be determined.
tags: inputs, dialect, encoding, delimiter, bom, locale
---

## Detect and Handle CSV Dialect Quirks

Impact: HIGH

Real-world CSVs are not all UTF-8 + comma. European
Excel exports use `;` as the delimiter. Some older
tools emit `windows-1252` (CP1252) or `latin-1`
encoded files. Files exported from a Windows tool
carry a UTF-8 BOM. Treat dialect detection as a
mandatory step before profiling the contents.

### Why it matters

Three concrete failure modes from skipping dialect
detection:

1. **Semicolon-delimited file read as comma-delimited.**
   Every row appears to have one column whose value
   is the entire row. The mapping fails because no
   column names match the schema.
2. **BOM byte at start of file.** The first column
   header becomes `﻿name` instead of `name`,
   and exact-match fails. The skill then either
   guesses or fails closed.
3. **Wrong encoding.** A `latin-1` file read as
   UTF-8 throws decode errors mid-file; the parsing
   stops partway and rows get silently dropped.

### Detection order

1. **Strip BOM.** If the file starts with `﻿`
   (UTF-8) or `￾`/`﻿` (UTF-16), strip
   before parsing. Always.
2. **Detect encoding.** Try UTF-8 first; on
   `UnicodeDecodeError`, try `windows-1252`, then
   `latin-1`. If none decode cleanly, fail closed
   with the byte offset of the first problem.
3. **Detect delimiter.** Sniff the first ~4KB:
   count `,`, `;`, and `\t` occurrences in the
   header line. The most frequent wins. If two are
   tied, prefer the extension hint (`.csv` → `,`;
   `.tsv` → `\t`). If still ambiguous, surface in
   the interview.
4. **Detect quote character.** Default `"`; switch
   to `'` only if `"` doesn't appear in the file
   at all.
5. **Detect line endings.** Read in binary, count
   `\r\n` vs `\n` in the first 4KB. Most CSV
   readers handle both transparently; record what
   was observed for the validate report.

### Locale-aware decimals

A column like `Memory_GB` in a European export may
carry `64,5` rather than `64.5`. If the delimiter
is `;` and the file contains numeric-looking cells
with `,`, treat `,` as the decimal separator after
the delimiter has been determined. See
[mapping-value-coercion.md](./mapping-value-coercion.md).

If both decimal-comma and thousands-comma are
present in the same column, surface in the
interview.

### Fail-closed dialect report

When detection can't disambiguate, fail closed with
a structured report:

```text
Cannot parse inventory.csv — dialect ambiguous.

Detected:
  - Encoding: utf-8 (clean)
  - BOM: none
  - Delimiter candidates: , (47 occurrences) | ; (51 occurrences)
  - Line endings: \r\n

The header line counts ; slightly more than , but the
file extension is .csv. Pick one:
  a) Comma-delimited
  b) Semicolon-delimited
  c) Inspect the file manually and re-run with the
     correct extension (.csv → comma, .tsv → tab)

No files have been written.
```

### Report the dialect with the plan

Before emission, echo the dialect choices alongside
the mapping plan:

```text
Parsed inventory.csv as:
  - Encoding: windows-1252
  - Delimiter: ;
  - Quote: "
  - Decimal separator: ,
```

Knowing the dialect later helps the user trace
unexpected values back to the input.

### Common mistakes

- **Trusting the extension blindly.** A `.csv` file
  with `;` delimiter is normal; the extension only
  hints. Sniff anyway.
- **Reading as `utf-8` and crashing on the first
  non-ASCII byte.** Latin-1 is a strict superset of
  ASCII for the first 128 codepoints; falling back
  is safe.
- **Stripping BOM with a literal `\xef\xbb\xbf`
  replace after decoding.** Decode first, then
  strip `﻿`. The byte form is encoding-
  dependent and brittle.
- **Re-detecting per row.** Detect once on the
  first ~4KB and lock the dialect. Mid-file
  changes mean the file is corrupted, not that
  detection should adapt.

Reference: [Infrahub Docs](https://docs.infrahub.app)
