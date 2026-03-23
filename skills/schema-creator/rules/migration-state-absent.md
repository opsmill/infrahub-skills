---
title: Schema Migration Patterns
impact: MEDIUM
tags: migration, state, absent, adding, removing
---

## Schema Migration Patterns

Impact: MEDIUM

Schema changes on live data require careful migration strategies.

### Removing an Attribute

Use `state: absent` to remove an attribute. Don't just delete it from the YAML.

```yaml
- name: old_field
  kind: Text
  state: absent                  # Marks for removal
```

### Adding a New Attribute Safely

Add as optional first (or with a default), then tighten later after data is populated.

**Risky -- adding mandatory attribute to existing data:**

```yaml
- name: serial_number
  kind: Text
  # optional defaults to false -- existing objects will fail!
```

**Safe -- two-step approach:**

```yaml
# Step 1: Add as optional
- name: serial_number
  kind: Text
  optional: true

# Step 2 (after populating data): Make mandatory with default
- name: serial_number
  kind: Text
  optional: false
  default_value: "unknown"
```

### Renaming an Attribute

No direct rename -- use a three-step migration:

1. Add new attribute (optional)
2. Migrate data from old to new (via script or manual update)
3. Remove old attribute with `state: absent`

### Changing Attribute Type

Safest approach:

1. Add new attribute with new type
2. Migrate data
3. Remove old attribute with `state: absent`

Reference: [validation.md](../validation.md) for
`infrahubctl` commands and branch-based schema changes.
