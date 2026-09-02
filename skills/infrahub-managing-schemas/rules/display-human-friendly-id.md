---
title: Set human_friendly_id on Nodes
impact: HIGH
tags: display, human_friendly_id, identity, generics, inheritance
---

## Set human_friendly_id on Nodes

Impact: HIGH

Every user-facing node carries a `human_friendly_id`
listing the attribute paths that identify it.

### Why it matters

Object data files reference peers by their
human-friendly id, not by UUID — without one,
loading data can only target objects by their
internal UUID, which is unknown until after the
object exists. The UI also falls back to UUID in
selectors and breadcrumbs, leaving users staring at
strings like `f47ac10b-58cc-…` instead of
`PowerEdge R960`. `default_filter` was the old name
for this concept and is deprecated; the loader
still parses it on older versions but it is removed
in current Infrahub, so any new schema should use
`human_friendly_id`.

**Incorrect -- no human_friendly_id:**

```yaml
nodes:
  - name: DeviceType
    namespace: Dcim
    # No human_friendly_id -- objects can't be easily referenced
```

**Correct:**

```yaml
nodes:
  - name: DeviceType
    namespace: Dcim
    human_friendly_id:
      - model__value               # Single element = scalar reference
```

### Path Syntax

- Local attributes: `attribute_name__value`
- Traverse relationships: `relationship__attribute__value`
- Multi-level: `parent__shortname__value`

### Single vs Multi-Element

| Elements | Reference Style | Example |
| -------- | --------------- | ------- |
| 1 element | Scalar | `device_type: PowerEdge R960` |
| 2+ elements | List | `rack: ["room-short", "Rack-A"]` |

### Examples

```yaml
# Simple -- referenced as: manufacturer: Dell
human_friendly_id:
  - name__value

# Composite -- referenced as: rack: ["01-4", "TEST-RACK1"]
human_friendly_id:
  - parent__shortname__value
  - name__value

# Through relationship -- referenced as: bay: ["PowerEdge R960", "PSU1"]
human_friendly_id:
  - device_type__model__value
  - name__value
```

### Scope on a generic: it resolves across every implementer

At schema load the `human_friendly_id` is compiled into
a `uniqueness_constraints` group on the entity that
declares it: attribute paths carry over as-is, and a
relationship path such as `parent__name__value`
collapses to the bare relationship `parent`.

So a `human_friendly_id` on a generic **is** a
generic-scoped uniqueness constraint, and it resolves
across **every kind that inherits it**. An upsert of one
kind can match an existing object of a *sibling* kind
that happens to share the same identifying values.

The error does not say so. On a non-default branch it
reads:

```text
Node <id> / <SiblingKind> uses this human-friendly ID, but does not exist on
this branch. Please rebase this branch to access <id> / <SiblingKind>
```

**The rebase advice is wrong.** The node exists; it is
simply not of the kind being upserted. The upsert path
looks the matched node up using the kind *you* asked
for, fails to find it under that kind, and reports the
miss as a stale branch. The `<id>` quoted belongs to
the sibling's object, and the kind named beside it is
the clue the message never explains. On the default
branch the same situation raises a plain not-found
instead.

If two implementers of a generic legitimately share
identifying values, the `human_friendly_id` belongs on
each concrete kind rather than on the generic.

That also means moving a `uniqueness_constraints` entry
off a generic and onto its concrete kinds is only half
the job: an HFID left behind on the generic puts the
same cross-kind check straight back, and the load error
then names a `uniqueness_constraints` entry that does
not appear in the file. Move both together. See
[uniqueness-constraints.md](uniqueness-constraints.md).

Pair with `display_label` for UI rendering (supports Jinja2):

```yaml
display_label: "{{ manufacturer__name__value }} {{ name__value }}"
```

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
