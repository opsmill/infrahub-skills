---
title: Translate Dropdown Labels to Choice Names
impact: CRITICAL
description: >-
  For every Dropdown attribute, build a label→name lookup from the
  schema's choices and translate each cell to the choice name before
  emitting. Cells matching neither a name nor a label route to the
  interview; never silent-drop or fuzzy-guess.
tags: mapping, dropdown, label, name, choices
---

## Translate Dropdown Labels to Choice Names

Impact: CRITICAL

For every Dropdown attribute, build a `label → name`
lookup from the schema's `choices` list. Translate
each CSV cell to the choice `name` before emitting.
Cells matching neither a label nor a name route to
the interview.

### Why it matters

Dropdown choices store the machine `name`; the UI
shows the `label`. The loader accepts only the
`name`. CSVs almost always carry labels (they were
exported from a UI or typed by humans), so passing
the cell verbatim fails every dropdown row with
`'Active' is not a valid choice for status`. Full
emission rules in
[../../infrahub-managing-objects/rules/value-attributes.md](../../infrahub-managing-objects/rules/value-attributes.md).

### How to build the lookup

For each Dropdown attribute in the schema:

```yaml
status:
  kind: Dropdown
  choices:
    - name: active
      label: Active
    - name: maintenance
      label: Maintenance
    - name: retired
      label: Retired
```

Build:

```python
status_lookup = {
    "active": "active",      # name → name (identity)
    "Active": "active",      # label → name
    "maintenance": "maintenance",
    "Maintenance": "maintenance",
    "retired": "retired",
    "Retired": "retired",
}
```

Match case-insensitively when the lookup misses on
exact case. If the CSV is `ACTIVE` and the lookup
has `Active`, treat it as a match.

### Always emit the name, never the label

**Incorrect — passing the label through:**

```yaml
data:
  - name: spine-01
    status: Active            # 'Active' is not a valid choice
    rack_face: Front
```

**Correct — emit the choice name:**

```yaml
data:
  - name: spine-01
    status: active            # the choice name from the schema
    rack_face: front
```

### Unmatched cells → interview

If a cell matches neither a name nor a label
(e.g., `status: "TBD"` when the schema's choices
are `active/maintenance/retired`), do not invent a
mapping and do not silently drop the row. Surface
the mismatch in the interview:

```text
Column "Status" has 3 cells whose value
matches no choice in DcimDevice.status:

  - "TBD"        (appears 4 times)
  - "Standby"    (appears 1 time)
  - "Spare"      (appears 2 times)

Schema choices: active, maintenance, retired.

How should I handle these?
  a) Map each to a specific choice (you tell me which)
  b) Treat as missing — emit no status for those rows
  c) Skip the rows entirely
  d) Add new dropdown choices (escalate to managing-schemas)
```

Option (d) is the only one that escalates — the
skill never adds dropdown choices on its own.

### Common mistakes

- **Lowercasing the cell and calling it a match.**
  Some labels include capitals deliberately
  (`Pre-Production`, `End-of-Life`); the
  lowercased form may collide with another
  choice's name. Use the lookup; don't guess.
- **Emitting the original case from the CSV.** The
  choice `name` is canonical regardless of how it
  was typed in the input.
- **Silently swapping similar-looking values.**
  `Spare` is not a typo for `retired`. Surface it.

Reference: [Infrahub Object Docs](https://docs.infrahub.app)
