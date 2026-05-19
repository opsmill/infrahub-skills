---
title: Computed Attributes with Jinja2 Templates
impact: HIGH
tags: attribute, computed_attribute, jinja2, read_only, derived
---

## Computed Attributes with Jinja2 Templates

Impact: HIGH

A `computed_attribute` derives its value from other
fields via a Jinja2 template. The system populates it
on every save, so the user must not be allowed to
write to it: pair `computed_attribute` with
`read_only: true` always. The `optional` setting
depends on how the value is used — keep it mandatory
when something else relies on it being present
(display label, `human_friendly_id`, uniqueness
constraints), make it optional when the derivation
is best-effort and an empty value is acceptable.

Common use cases seen across production schemas:

- Deterministic display name from foreign keys
  (`"AS{{asn__value}}"` for a BGP AS, contract names
  built from circuit IDs)
- Concatenated identifiers for service objects
  (`"{{ deployment__name__value }} - {{ customer__name__value }}"`)
- Status descriptors or human-readable summaries
  built from operational fields

### Required Pairing

```yaml
- name: name
  kind: Text
  computed_attribute:
    kind: Jinja2
    jinja2_template: "AS{{ asn__value }}"
  read_only: true                # ALWAYS — system writes; block user input
```

That's the minimum. `read_only: true` is non-negotiable
whenever `computed_attribute` is present.

### When `optional: false` Is Right

Mark it mandatory if downstream features assume the
value is always populated:

- The attribute is referenced by `display_label`
- The attribute appears in `human_friendly_id`
- The attribute is part of a
  `uniqueness_constraints` entry
- The Jinja2 template inputs are themselves all
  mandatory, so the derivation is total

```yaml
- name: name
  kind: Text
  computed_attribute:
    kind: Jinja2
    jinja2_template: "AS{{ asn__value }}"
  read_only: true
  optional: false                # Required: used as display_label
  unique: true
```

### When `optional: true` Is Fine

Leave it optional if the value is purely
informational and may legitimately be empty when
inputs are missing:

```yaml
- name: summary
  kind: Text
  computed_attribute:
    kind: Jinja2
    jinja2_template: >-
      {{ check__value }}-{{ rise__value | default('?') }}
  read_only: true
  optional: true                 # Informational only — empty OK
```

This is the path to take if any input attribute is
itself optional and you don't want the whole record
to fail validation when it's unset.

### Why each field matters

- **`read_only: true`** — without this, users can
  edit the field directly. The system also
  recomputes on save, so user edits would be silently
  overwritten. The Infrahub validator rejects
  computed attributes that are not read-only.
- **`optional`** — choose based on whether the
  derived value is load-bearing. Mandatory expresses
  "the inputs guarantee a value"; optional expresses
  "absence is acceptable." Don't pick mandatory by
  habit — if any input is itself optional, mandatory
  here will make the parent record fail to save.
- **`kind: Jinja2`** under `computed_attribute` —
  selects the engine. This is the only currently
  supported kind for derived attributes.

### Template Variable Reference Format

Jinja2 templates reference other attributes and
related-object attributes with the `__value` suffix
and `__` separators for relationship traversal:

| Reference | Meaning |
| --------- | ------- |
| `{{ asn__value }}` | Local attribute `asn` |
| `{{ circuit__circuit_id__value }}` | `circuit` rel → `circuit_id` attribute |
| `{{ vip_ip__address__value }}` | `vip_ip` rel → `address` attribute |

The traversal depth is one relationship hop deep.
Use `display_label` on the peer node if you need a
formatted representation rather than reaching across
two hops.

### Antipatterns

**Missing `read_only: true`:**

```yaml
# WRONG — user can write a value the system will overwrite
- name: name
  kind: Text
  computed_attribute:
    kind: Jinja2
    jinja2_template: "AS{{ asn__value }}"
  optional: false
```

**Mandatory derivation that depends on optional
inputs:**

```yaml
# WRONG — description is mandatory but build inputs may be unset,
# so the parent record will fail to save when they are
- name: description
  kind: Text
  computed_attribute:
    kind: Jinja2
    jinja2_template: "{{ check__value }}-{{ rise__value }}"
  read_only: true
  optional: false                # Inputs are optional → make this optional too
```

**Forgetting `unique: true` when the derived value
is identifying:** if the computed attribute is the
display label or part of `human_friendly_id`, set
`unique: true` so duplicates are rejected at write
time instead of breaking the UI silently.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
