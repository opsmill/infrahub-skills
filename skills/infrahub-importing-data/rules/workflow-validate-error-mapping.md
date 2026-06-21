---
title: Translate Server Validate Errors Back to CSV Cells
impact: LOW
description: >-
  When `infrahubctl object validate` reports a failure, translate the error
  message — file + row + attribute — back to the input CSV cell that
  produced it. Surface the source coordinates so the user can fix the input
  in one pass, not the YAML.
tags: workflow, validate, errors, traceback, ux
---

## Translate Server Validate Errors Back to CSV Cells

Impact: LOW

After step 11 (`infrahubctl object validate
./output_dir/ --branch <name>`), if validate fails,
the server returns a message that names the emitted
YAML file, row, and attribute. Translate that
coordinate back to the source CSV file, line, and
column so the user fixes the *input*, not the
emitted YAML — re-running with a corrected CSV is
the supported flow.

### Why it matters

Letting the user edit the emitted YAML by hand to
unblock validate is a short-term fix that drifts
the YAML away from the source CSV. The next re-run
overwrites the manual edit. Always trace the error
back to the input and ask the user to fix it there.

The skill knows the mapping table that produced
each YAML row, so the translation is mechanical —
no manual cross-referencing required.

### The translation template

When validate emits something like:

```text
output_dir/04_devices.yml row 7 attribute 'status':
  'Active' is not a valid choice for status
```

Translate to:

```text
inventory.csv row 12 column "Status":
  cell value "Active" is the display label, not the
  choice name. The schema's DcimDevice.status choices are:
    active / maintenance / retired

Fix options:
  a) Edit inventory.csv row 12 "Status" to "active"
  b) Edit inventory.csv "Status" column globally to use names
  c) Re-run this skill — the dropdown-label-to-name rule
     would have translated this automatically; the prior
     run may have skipped it (see the interview log)

The emitted YAML will be regenerated; do not edit it directly.
```

### Required mapping table

Maintain a per-row backreference during emission so
the translation is O(1):

```text
emitted_row[(file, row_index, attribute)]
  → source_csv[(input_file, csv_line_number, column_name)]
```

Component children inherit the source coordinates
of their parent row. Range-collapsed entries
inherit the coordinate range of the rows they
replaced — `inventory.csv rows 8–55 (interface_name
column)`.

### Common validate errors and their input causes

| Validate error | Likely CSV cause | Pointer rule |
| -------------- | ---------------- | ------------ |
| `'X' is not a valid choice for Y` | Dropdown cell carries label instead of name | [mapping-dropdown-label-to-name.md](./mapping-dropdown-label-to-name.md) |
| `Reference target not found: <kind> <hfid>` | Orphan reference; upstream file missing the row | [workflow-pre-flight-closure.md](./workflow-pre-flight-closure.md) |
| `Expected boolean, got 'Yes'` | Boolean coercion missed | [mapping-value-coercion.md](./mapping-value-coercion.md) |
| `Required attribute X not provided` | Blank required cell | [mapping-empty-and-null.md](./mapping-empty-and-null.md) |
| `Unknown attribute X on kind Y` | Mapping bound to an attribute that doesn't exist on the kind | [mapping-column-to-attribute.md](./mapping-column-to-attribute.md) |

### When the error has no clean translation

Some validate errors are at the file level (e.g.,
`spec.kind missing`) and don't trace back to a CSV
cell. Surface them as emitter bugs and re-run the
self-check
([workflow-self-check-against-managing-objects.md](./workflow-self-check-against-managing-objects.md))
— the self-check should have caught it locally.

### Common mistakes

- **Telling the user to edit the YAML directly.**
  The next re-run wipes the edit. Always route to
  the source CSV.
- **Re-running validate after editing the YAML.**
  Validate passes; the next run regenerates the
  YAML from the unchanged CSV and the error
  returns.
- **Summarizing many errors as "fix these in the
  CSV" without naming the specific cells.** The
  user has to grep their CSV manually. Always
  emit per-cell coordinates.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
