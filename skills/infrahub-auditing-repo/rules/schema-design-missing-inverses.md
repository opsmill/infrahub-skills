---
title: schema-design-missing-inverses
impact: HIGH
tags: audit, schema, relationships, inverses
---

# Rule: schema-design-missing-inverses

**Severity**: HIGH
**Category**: Schema Design

## What It Checks

Identifies `kind: Attribute` relationships with
`cardinality: one` whose peer node (or any generic
it inherits from) does not declare an inverse
relationship back to the source. The inverse is
free to add — the platform already knows the link
exists from the forward side — and missing
inverses force generators, checks, and ad-hoc
queries to fetch the entire peer collection and
filter in code instead of walking one hop from
the focal node.

## Why it matters

Infrahub relationships are conceptually
bidirectional, but the schema only auto-creates
the reverse traversal when both sides are
declared with matching `identifier` values.
Declaring only the forward side is technically
valid YAML — schema check passes, the platform
loads cleanly — but the reverse query path simply
doesn't exist. A consumer who has the peer in
hand and wants the source has no choice but to
query the source kind by some other anchor and
filter, which inflates query size and pushes
filtering logic into Python.

The downstream tell for a missing inverse is
exactly the cascade-shape pattern caught by
[xref-design-cascade-shape](./xref-design-cascade-shape.md):
a generator anchored on the peer ends up with a
top-level section for the source kind purely so
it can match by attribute equality in a Python
loop. The schema is forcing the inefficient
shape; the Python is paying the cost. Adding the
inverse removes both — the query traverses, the
loop disappears.

Missing inverses are also a maintainability cost.
Each new consumer of the same data rediscovers
the gap and writes its own workaround query, so
the same anti-pattern proliferates across
generators, checks, and transforms over time.

## Checks

1. **Inventory forward rels**: walk every node
   and generic across all schema files. For each
   relationship with `kind: Attribute` and
   `cardinality: one`, record the tuple
   `(source_kind, identifier, peer_kind)`.

2. **Inventory inverse rels on peers**: for each
   recorded peer kind, collect every relationship
   declared on the peer kind itself **and** every
   relationship declared on any generic the peer
   kind inherits from (`inherit_from`). Use the
   `identifier` field as the join key.

3. **Match by identifier**: for each forward tuple
   `(source_kind, identifier, peer_kind)`, look
   for any relationship on `peer_kind` (or its
   generics) whose `identifier` equals the
   forward `identifier` and whose `peer` is the
   `source_kind` (or any generic the source kind
   inherits from). If none exists, the inverse is
   missing.

4. **Filter trivial false positives**: skip
   `kind: Parent` and `kind: Component`
   relationships — those are paired structurally
   and covered by
   [schema-relationships](./schema-relationships.md).
   Skip self-referential rels (source kind equals
   peer kind) where the same rel acts as its own
   inverse.

5. **Account for `extensions` blocks**: a missing
   inverse on a node defined elsewhere may be
   supplied via an `extensions:` block in a
   different schema file. Include every
   `extensions:` block in the inverse inventory
   before deciding a rel is unmatched.

## Common Issues

- `InfraDevice` has `interfaces`
  (cardinality: many) but `InfraInterface` has no
  inverse `device` rel — every consumer that has
  an interface ID has to filter devices by
  membership.
- A new `cardinality: one` rel added to a node
  during a feature build with no thought to the
  consumer pattern; the next generator that
  needs the reverse direction writes a
  filter-in-Python workaround instead.
- Inverse declared on the wrong identifier
  (typo, or `peer__source` vs `source__peer`
  ordering inconsistency) — the rule will flag
  this; cross-check against
  [schema-relationships](./schema-relationships.md)
  rule 2 (bidirectional identifiers).

## Related

- Downstream Python/query symptom:
  [xref-design-cascade-shape](./xref-design-cascade-shape.md).
  Cascade-shape findings on a generator are
  often a flag that this rule will fire on its
  schema too.
- Identifier and cardinality fundamentals:
  [schema-relationships](./schema-relationships.md).
