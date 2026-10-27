---
title: Schema Migration Patterns
impact: MEDIUM
tags: migration, state, absent, adding, removing
---

## Schema Migration Patterns

Impact: MEDIUM

Schema changes on data that is already loaded follow
a staged migration — mark removals with
`state: absent`, add new fields as optional first,
and split type changes into add/migrate/remove.

### Why it matters

Deleting an attribute from the YAML does not remove
it from the data: the loader sees a field that
"disappeared" rather than one explicitly retired, and
the column lingers in the underlying graph attached
to every existing object. Adding a mandatory
attribute without a default fails validation for
every pre-existing record on the next load, blocking
the schema update entirely. The asymmetry — schema
changes are cheap before data is loaded, expensive
after — is what makes a planned migration sequence
mandatory once a node has live instances.

### Removing an Attribute

Use `state: absent` to remove an attribute rather
than deleting it from the YAML.

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
