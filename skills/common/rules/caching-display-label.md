---
title: Display Label Caching with Parent Relationships
impact: MEDIUM
tags: display-label, parent, caching, batch-loading, object-loading
---

## Display Label Caching with Parent Relationships

Impact: MEDIUM

When a node's `display_label` template references a Parent
relationship (e.g.,
`{{ device__name__value }} / {{ slot_name__value }}`),
the label may compute incorrectly during batch object
loading. The Parent relationship may not be fully resolved
when `display_label` is first computed, resulting in `None`
values.

### Symptoms

After loading objects via `infrahubctl object load`, nodes
with Parent-referencing display labels show `None` in place
of the parent's attribute:

```text
None / PSU1          # Expected: "TEST-R660xs-1 / PSU1"
None / NIC-OCP       # Expected: "TEST-R870-1 / NIC-OCP"
```

### Cause

`display_label` is computed at object creation time and
cached. During batch loading, the Parent relationship may
not be established when the label is first generated.

### Fix

Run a no-op update (mutation) on affected objects to force
display label recalculation:

```graphql
mutation {
  DcimModuleInstallationUpdate(
    data: {
      id: "<object-id>",
      description: { value: "" }
    }
  ) {
    ok
  }
}
```

For many objects, script the update in a loop. Any attribute
change (even setting description to empty string) triggers
recalculation.

### Prevention

When designing schemas with `display_label` templates that
reference Parent relationships, be aware this caching
behavior exists. Loading the parent objects first and child
objects second reduces (but doesn't eliminate) the issue.

Reference:
[Infrahub Display Label Docs](https://docs.infrahub.app/topics/schema/#display_label)
