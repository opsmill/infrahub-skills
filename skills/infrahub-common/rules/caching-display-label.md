---
title: Display Label Caching with Parent Relationships
impact: MEDIUM
tags: display-label, parent, caching, batch-loading, object-loading
---

## Display Label Caching with Parent Relationships

Impact: MEDIUM

A `display_label` template that reads through a Parent
relationship is computed and cached at insert time, so
a child loaded before its parent renders with `None`
in place of the parent's attribute.

### Why it matters

`infrahubctl object load` walks the YAML files in
whatever order they appear and doesn't reorder by
relationship dependency. If a child object is created
before the Parent it references, the template
evaluates against an empty peer and the resulting
string (`None / PSU1`) is what Infrahub caches —
later resolving the parent doesn't invalidate the
cache. Users see broken-looking display labels in the
UI and in any GraphQL query that returns
`display_label`, and they almost always assume the
template itself is wrong rather than the load order.

### Symptoms

After loading objects via `infrahubctl object load`,
nodes with Parent-referencing display labels show
`None` in place of the parent's attribute:

```text
None / PSU1          # Expected: "TEST-R660xs-1 / PSU1"
None / NIC-OCP       # Expected: "TEST-R870-1 / NIC-OCP"
```

### Cause

`display_label` is computed at object creation time
and cached. During batch loading, the Parent
relationship may not be established when the label is
first generated.

### Fix

Run a no-op update (mutation) on affected objects to
force display label recalculation:

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

For many objects, script the update in a loop. Any
attribute change (even setting description to empty
string) triggers recalculation.

### Prevention

Order the object files so parents load before their
children — Infrahub processes them in file order, and
pre-loading the parent set means the template has a
resolved peer when the cache is written. This reduces
the issue substantially but doesn't fully eliminate it
for circular or deeply nested hierarchies; keep the
no-op mutation handy as a recovery path.

Reference:
[Infrahub Display Label Docs](https://docs.infrahub.app/topics/schema/#display_label)
