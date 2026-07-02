---
title: yagni-duplicate-shape-not-extracted-to-generic
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, schema, generic
---

# Rule: yagni-duplicate-shape-not-extracted-to-generic

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — Already in this codebase?

## What It Checks

Three or more nodes that share the same attribute set (and often the
same relationships) without extracting the shared shape into a
generic with `inherit_from`. The duplication is data the schema is
forcing reviewers to keep in sync by hand.

## Why it matters

When `name`, `status`, `description`, `owner` appear identically on
six nodes, a change to one (rename, type tightening, new default)
silently diverges the others. Schema reviews stop catching the drift
once it spans more than two files. A generic centralises the shape
in one place; nodes pick it up via `inherit_from`, which is the
mechanism the platform expects. Indexing, GraphQL fragment reuse, and
SDK type generation also collapse to one definition instead of N.

## Checks

1. Three or more nodes whose attribute lists are >70% identical by
   name and kind. Likely candidates for a shared generic.
2. Repeated attribute blocks across nodes for `name`, `description`,
   `status`, `owner`, `notes` — the canonical "common metadata"
   bundle. Move to a `Generic` base.
3. Two or more nodes already inheriting from the same generic that
   duplicate *additional* attributes between themselves. Promote the
   shared additional attributes into the generic or a second generic.
4. Pairs of nodes with identical relationship blocks (peer kinds,
   identifiers, cardinality) — the relationship belongs on a shared
   generic.

## What NOT to flag

- Two nodes sharing one or two trivial attributes (`name`,
  `description`). The cost of a generic exceeds the duplication.
- Nodes that share attribute *names* but differ in kind or
  constraints (one's `id` is `Text`, another's is `Number`). They
  aren't the same shape.
- Nodes already inheriting from `opsmill/schema-library` generics
  where the shared attributes come from the library — that's reuse,
  not duplication.
- Domain-specific generics that exist for documentation purposes
  even when only one node currently inherits them (the second
  consumer is planned).

## Common Issues

- Six device-type nodes (`DeviceSpine`, `DeviceLeaf`, `DeviceEdge`,
  ...) each repeating the same 10 attributes. One `DeviceCommon`
  generic + six minimal nodes.
- A new node copy-pasted from an existing one without converting the
  shared block to inheritance.
- `Site`, `Region`, `Country` repeating the same metadata fields
  instead of inheriting from a `LocationBase` generic.
