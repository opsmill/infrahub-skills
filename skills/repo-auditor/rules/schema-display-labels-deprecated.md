# Rule: schema-display-labels-deprecated

**Severity**: HIGH
**Category**: Schema

## What It Checks

Detects usage of the deprecated `display_labels` field
(plural, list format) in schema files and provides
exact migration instructions to the replacement
`display_label` field (singular, Jinja2 template
string). Deprecated since Infrahub v1.5.

## Checks

1. Scan all schema files for any node or generic
   containing the `display_labels` key
2. For each occurrence, flag as HIGH severity — this
   field will be removed in a future release
3. Generate the exact `display_label` Jinja2
   replacement based on the list contents

## Migration Patterns

### Single attribute

**Before:**

```yaml
display_labels:
  - "name__value"
```

**After:**

```yaml
display_label: "{{ name__value }}"
```

### Multiple attributes

**Before:**

```yaml
display_labels:
  - "form_factor__value"
  - "sfp_type__value"
```

**After:**

```yaml
display_label: "{{ form_factor__value }} {{ sfp_type__value }}"
```

### With relationship traversal

**Before:**

```yaml
display_labels:
  - "device__name__value"
  - "name__value"
```

**After:**

```yaml
display_label: "{{ device__name__value }}>{{ name__value }}"
```

## Conversion Algorithm

1. Remove the `display_labels` key entirely
2. Create a `display_label` key with a single Jinja2
   template string
3. Wrap each former list item in `{{ }}` delimiters
4. Join multiple items with a space separator (or `>`
   for hierarchical relationships — use judgement
   based on context)
5. The result is a single string, not a list

## Validation

Run `infrahubctl schema check <path/to/schema/files>`
to confirm the migrated schema is valid.

## Common Issues

- Leaving `display_labels` as-is — currently works
  with a deprecation warning but will break in a
  future Infrahub release
- Forgetting the `__value` suffix inside Jinja2
  templates — the template uses the same path syntax
  as the old list items
- Using a list for `display_label` instead of a single
  Jinja2 string — `display_label` takes a string,
  not a list
