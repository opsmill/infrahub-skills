---
title: schema-relationships
impact: CRITICAL
tags: audit, schema, relationships
---

# Rule: schema-relationships

**Severity**: CRITICAL
**Category**: Schema

## What It Checks

Validates relationship definitions: peer kinds use
the full namespace+name reference, the
`identifier` is identical on both sides of the
link, and Component/Parent pairs use the
cardinalities they require.

## Why it matters

Mismatched relationship identifiers are the
single most common schema bug and the hardest to
diagnose: each side loads as a one-way edge, so
the platform reports no error, the UI shows the
relationship on one node, and queries from the
other side return empty — looking exactly like a
data problem rather than a schema problem.
Short-form peer references (`peer: Device`
instead of `peer: InfraDevice`) fail at schema-
load time with a cryptic "kind not found" because
the resolver doesn't search across namespaces.
Component with `cardinality: one` produces the
strangest UX of all: deleting the parent silently
also deletes the single child, which works until
someone adds a second child and the schema
rejects it without explaining why.

## Checks

1. **Peer kind**: every `peer` field uses full kind
   (Namespace + Name), not just name
2. **Bidirectional identifiers**: both sides of a relationship share the same `identifier`
3. **Identifier convention**: uses `__` separator (e.g., `parent__children`)
4. **Component relationships**: have `kind: Component` and `cardinality: many`
5. **Parent relationships**: have `kind: Parent` and `cardinality: one`
6. **Component/Parent pairs**: share the same `identifier`
7. **Default awareness**: cardinality defaults to `many`,
   optional defaults to `true` — flag when these
   defaults may cause confusion

## Common Issues

- `peer: Device` instead of `peer: InfraDevice`
- Mismatched identifiers between two sides of a bidirectional relationship
- Component side with `cardinality: one` (should be `many`)
- Parent side with `cardinality: many` (should be `one`)
