---
title: Coerce Cell Strings Into Native Attribute Types
impact: CRITICAL
description: >-
  CSV cells are always strings; non-Text attribute types
  (Number, Boolean, DateTime, JSON) require explicit
  coercion before emission. Boolean cells emit YAML booleans,
  Number cells emit integers/floats, DateTime cells emit
  ISO-8601 strings. Ambiguous cells route to the interview.
tags: mapping, coercion, types, boolean, number, datetime, json
---

## Coerce Cell Strings Into Native Attribute Types

Impact: CRITICAL

CSV files carry every value as a string. The Infrahub
loader accepts YAML, which distinguishes booleans,
numbers, and strings. Emitting `is_managed: "Yes"`
when the schema declares `is_managed: Boolean` either
fails the load or coerces silently to a truthy string,
not to `true`. Coerce in the emitter, never trust the
raw cell.

### Why it matters

Three concrete failure modes if coercion is skipped:

1. **Boolean rejection.** `'Yes' is not a valid value
   for is_managed (expected boolean)` — the load
   stops at the first row.
2. **Number-as-string silent acceptance.** Some
   attribute types accept the string form and coerce
   internally, but ordering and arithmetic
   afterwards behaves like text (`"10" < "9"`).
3. **DateTime mismatch.** A column like `01/15/2024`
   parses as a string into a `DateTime` attribute
   only when the format matches ISO-8601; otherwise
   the load fails or stores a wrong instant.

### Coercion ladder per attribute type

Apply per-cell based on the **schema's declared
attribute kind**, not the cell's content shape.

| Schema kind | Accepted CSV forms | Emit as |
| ----------- | ------------------ | ------- |
| `Boolean` | `true`/`false`, `yes`/`no`, `1`/`0`, `y`/`n`, `t`/`f` (case-insensitive) | YAML boolean `true` / `false` |
| `Number` | `42`, `42.0`, `1_000`, `1,000` (after stripping `,` thousands separator) | YAML integer or float |
| `DateTime` | ISO-8601, `YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS`, `MM/DD/YYYY`, `DD/MM/YYYY` | ISO-8601 string (`2024-01-15T00:00:00Z` or `2024-01-15`) |
| `JSON` | Valid JSON string in the cell | Parsed YAML/JSON value (not the raw string) |
| `Text` / `TextArea` / `URL` / `IPHost` / `IPNetwork` / `Email` | Anything | Pass through verbatim (trimmed of leading/trailing whitespace) |

For `MM/DD/YYYY` vs `DD/MM/YYYY` ambiguity, route to
the interview — there is no safe heuristic when both
`01/02/2024` and `02/01/2024` could be either. The
interview question names the column and shows the
first 3 cell samples.

### Incorrect — pass-through

```yaml
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      is_managed: "Yes"          # boolean attribute rejects
      gpu_count: "8"              # number attribute, string sneaks in
      commissioned_at: "01/15/2024"  # datetime, ambiguous format
```

### Correct — coerced before emission

```yaml
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      is_managed: true            # boolean
      gpu_count: 8                # integer
      commissioned_at: "2024-01-15"  # ISO-8601
```

### Number-with-units in the cell

A cell like `Memory (GB)` → `64GB` should never sneak
the unit suffix into a Number attribute. If the
column header carries the unit (the unit-strip step
in [mapping-column-to-attribute.md](./mapping-column-to-attribute.md)
covered it), the cell value should be unit-free; if
the cell carries its own unit (`64GB` rather than
`64`), surface in the interview — the unit might not
match the schema's declared unit.

### JSON attribute

A `JSON`-kind attribute expects the parsed value, not
the raw string:

```yaml
# CSV cell: '{"vlan": 100, "tagged": true}'

# Incorrect
metadata: '{"vlan": 100, "tagged": true}'

# Correct
metadata:
  vlan: 100
  tagged: true
```

If the cell isn't valid JSON, surface in the
interview rather than emit a malformed mapping.

### Boolean coercion — case-insensitive lookup

```python
TRUE_FORMS = {"true", "yes", "y", "t", "1"}
FALSE_FORMS = {"false", "no", "n", "f", "0"}

def to_bool(cell: str) -> bool | None:
    s = cell.strip().lower()
    if s in TRUE_FORMS: return True
    if s in FALSE_FORMS: return False
    return None  # → surface in interview
```

Anything outside both sets — `maybe`, `tbd`,
`partial` — routes to the interview, never silently
emits `false`.

### Common mistakes

- **Treating every cell as Text.** Works for `Text`
  but corrupts `Boolean`, `Number`, `DateTime`,
  and `JSON` attributes.
- **Auto-coercing on cell shape (`"42"` → 42)
  regardless of the attribute kind.** A
  `serial_number` attribute declared as `Text` that
  happens to contain only digits must stay a string;
  emitting it as a YAML int loses leading zeros
  and changes ordering. The schema is the source of
  truth, not the cell.
- **Locale-confused decimals.** A European export
  may use `,` as the decimal separator (`64,5`).
  Strip thousands separators first, then check
  whether the remaining `,` is a decimal point —
  and surface in the interview if the convention
  isn't obvious.
- **DateTime in epoch seconds.** A column with raw
  Unix timestamps (`1705276800`) needs explicit
  conversion. Don't store the int into a DateTime
  attribute and hope.

Reference: [Infrahub Attribute Kinds](https://docs.infrahub.app/reference/schema/attribute)
