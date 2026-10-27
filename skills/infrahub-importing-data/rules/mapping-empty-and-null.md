---
title: Handle Empty Cells by Schema Optionality
impact: HIGH
description: >-
  A blank CSV cell becomes either an omitted attribute (when the schema
  declares the attribute optional or supplies a default) or a fail-closed
  diagnostic (when the attribute is required and has no default). Never
  emit an empty-string scalar for a missing value.
tags: mapping, null, empty, optional, default
---

## Handle Empty Cells by Schema Optionality

Impact: HIGH

CSV cells can be blank for three different reasons:
the value is unknown, the value is intentionally
absent, or the export tool stripped it. The emitter
can't tell which — only the schema can. Use the
schema's `optional` and `default_value` declarations
to decide whether to omit the attribute or fail
closed.

### Why it matters

Emitting an empty string `""` for a blank cell:

1. **Stores empty strings as real data.** A
   `description` column with 800 blank cells becomes
   800 rows with `description: ""` in the database,
   indistinguishable from rows where the user
   deliberately set an empty description.
2. **Bypasses the schema's `optional: false`
   guarantee.** A required attribute with `""` is
   technically present, so the load doesn't reject —
   but a downstream check expecting a non-empty
   value will fail later, far from the import.
3. **Wrong for non-Text types.** A blank cell on a
   `Number` attribute can't become `""` — the load
   rejects with a type error and the whole batch
   aborts.

### Decision matrix

For each blank cell, look up the schema attribute:

| Schema declaration | Action |
| ------------------ | ------ |
| `optional: true`, no `default_value` | Omit the attribute from the row's mapping entirely |
| `optional: true`, `default_value: <X>` | Omit the attribute; the loader applies the default |
| `optional: false`, no `default_value` | **Fail closed**: surface the blank cells in the interview before emission. Never emit a placeholder |
| `optional: false`, `default_value: <X>` | Omit the attribute; the default fills in |

The "omit the attribute" form is the difference
between an attribute being unset (so checks and
generators can detect the absence) and being set to
an empty string (silently present).

### Correct — omit on optional

CSV:

```csv
name,description,country
Dell,Server vendor,US
Juniper,,US
Arista,,
```

Schema: `description` and `country` both
`optional: true` on `OrganizationManufacturer`.

```yaml
spec:
  kind: OrganizationManufacturer
  data:
    - name: Dell
      description: Server vendor
      country: US
    - name: Juniper
      country: US                # description omitted, not ""
    - name: Arista               # description AND country omitted
```

### Incorrect — empty-string scalar

```yaml
spec:
  kind: OrganizationManufacturer
  data:
    - name: Dell
      description: Server vendor
      country: US
    - name: Juniper
      description: ""            # WRONG — pollutes the data
      country: US
    - name: Arista
      description: ""            # WRONG
      country: ""                # WRONG
```

### Correct — fail closed on required

CSV:

```csv
name,role,site
spine-01,spine,
leaf-02,,par-1
```

Schema: `DcimDevice.role` and `DcimDevice.site` both
`optional: false`, no defaults.

```text
Cannot import: 2 required values are blank.

inventory.csv:
  - row 2 (spine-01): "site" is blank but DcimDevice.site is required (no default)
  - row 3 (leaf-02):  "role" is blank but DcimDevice.role is required (no default)

Options:
  a) Supply the missing values in the source CSV and re-run
  b) Add a default_value to the schema attribute (escalate to managing-schemas)

No files have been written.
```

### What counts as blank

Treat as blank: empty cell `,,`, whitespace-only
cell `, ,`, and the literal strings `NULL`, `N/A`,
`#N/A`, `-`, `<blank>` (case-insensitive). The
interview can extend this list per-column when the
source uses a custom sentinel.

### Relationships and component children

For a blank reference cell:

- `optional: true` relationship → omit the
  relationship key entirely (do not emit
  `manufacturer: null` or `manufacturer: ""`).
- `optional: false` relationship → fail closed
  with the same diagnostic as required attributes.

For cardinality:many relationships, an empty cell
means "no members" — emit either an empty list `[]`
or omit the key. Omit is preferred unless the
loader documentation specifies the list form for
"clear all members" semantics.

### Common mistakes

- **Emitting `null` (YAML literal).** Sometimes
  accepted, sometimes rejected, varies by attribute
  kind. Omitting the key is universally safe.
- **Treating whitespace-only as a non-blank
  value.** Spreadsheet exports often have trailing
  whitespace; strip first, then check for blank.
- **Failing only on the first blank required
  cell.** Surface every blank required cell in one
  diagnostic so the user can fix the source in one
  pass.
- **Quietly substituting a default at emit time.**
  Apply defaults by *omission*; let the loader fill
  them. Substituting in the emitter prints the
  default in audit trails as if the import supplied
  it, hiding the fact that the source CSV was
  blank.

Reference: [Infrahub Attribute Properties](https://docs.infrahub.app/reference/schema/attribute)
