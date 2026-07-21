---
title: yagni-missing-inverse-forces-python-filter
impact: MEDIUM
ladder_step: 3
tags: audit, yagni, schema, relationships, inverses
---

# Rule: yagni-missing-inverse-forces-python-filter

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 3 — Can a schema feature express it?

## What It Checks

`kind: Attribute` relationships with `cardinality: one` whose peer
node (or any generic it inherits from) does not declare a matching
inverse relationship back to the source. The inverse is free to add
— the platform already knows the link exists from the forward side —
and missing inverses force generators, checks, and ad-hoc queries to
fetch the entire peer collection and filter in code instead of
walking one hop from the focal node.

## Why it matters

Infrahub relationships are conceptually bidirectional, but the schema
only auto-creates the reverse traversal when both sides are declared
with matching `identifier` values. Declaring only the forward side is
technically valid YAML — schema check passes, the platform loads
cleanly — but the reverse query path simply doesn't exist. A consumer
who has the peer in hand and wants the source has no choice but to
query the source kind by some other anchor and filter, which inflates
query size and pushes filtering logic into Python.

The downstream tell is the cascade-shape pattern caught by
[yagni-generator-query-shape-too-broad](./yagni-generator-query-shape-too-broad.md):
a generator anchored on the peer ends up with a top-level section for
the source kind purely so it can match by attribute equality in a
Python loop. The schema is forcing the inefficient shape; the Python
is paying the cost. Adding the inverse removes both — the query
traverses, the loop disappears.

Missing inverses are also a maintainability cost. Each new consumer
of the same data rediscovers the gap and writes its own workaround
query, so the same anti-pattern proliferates across generators,
checks, and transforms over time.

## Checks

1. **Inventory forward rels**: walk every node and generic across all
   schema files. For each relationship with `kind: Attribute` and
   `cardinality: one`, record the tuple
   `(source_kind, identifier, peer_kind)`.
2. **Inventory inverse rels on peers**: for each recorded peer kind,
   collect every relationship declared on the peer kind itself **and**
   every relationship declared on any generic the peer kind inherits
   from (`inherit_from`). Use the `identifier` field as the join key.
3. **Match by identifier**: for each forward tuple
   `(source_kind, identifier, peer_kind)`, look for any relationship
   on `peer_kind` (or its generics) whose `identifier` equals the
   forward `identifier` and whose `peer` is the `source_kind` (or any
   generic the source kind inherits from). If none exists, the
   inverse is missing.
4. **Filter trivial false positives**: skip `kind: Parent` and
   `kind: Component` relationships — those are paired structurally
   and covered by
   [schema-relationships](./schema-relationships.md). Skip
   self-referential rels (source kind equals peer kind) where the
   same rel acts as its own inverse.
5. **Account for `extensions` blocks**: a missing inverse on a node
   defined elsewhere may be supplied via an `extensions:` block in a
   different schema file. Include every `extensions:` block in the
   inverse inventory before deciding a rel is unmatched.

## What NOT to flag

- `kind: Parent` and `kind: Component` relationships — structural
  pairs already covered by `schema-relationships`.
- Self-referential relationships where the source equals the peer
  and the same rel acts as its own inverse.
- Forward rels where the peer side's inverse is declared via
  `extensions:` in a different schema file (include extension blocks
  in the inverse inventory before flagging).
- Forward rels declared on a generic where the inverse is declared
  on the same generic's mirror (and the concrete nodes inherit both
  sides).

## Common Issues

- `InfraInterface.device` is declared with `kind: Attribute` and
  `cardinality: one` but `InfraDevice` declares no inverse
  `interfaces` relationship. Every consumer that has an interface ID
  in hand has to query devices and filter by membership instead of
  traversing one hop.
- A new `cardinality: one` rel added to a node during a feature build
  with no thought to the consumer pattern; the next generator that
  needs the reverse direction writes a filter-in-Python workaround
  instead.
- Inverse declared on the wrong identifier (typo, or
  `peer__source` vs `source__peer` ordering inconsistency) — the
  rule will flag this; cross-check against
  [schema-relationships](./schema-relationships.md) rule 2
  (bidirectional identifiers).

## Fixing it: match the forward side's existing identifier

When you add the inverse, it must carry the **same
`identifier` as the forward relationship already has**
— not a freshly-invented `peer__source` string. If
the forward relationship is already loaded in a
running instance without an explicit identifier,
Infrahub auto-generated one
(`"__".join(sorted([kind, peer])).lower()`), and the
identifier is now immutable. Reusing that exact value
on the new inverse connects the two into one
bidirectional edge; inventing a new string and
changing the forward side to match instead fails
`infrahubctl schema check` with
`'not_supported': <Kind> <rel> None`, because
`identifier` cannot be changed after load.

So: read the forward relationship's current
`identifier` (from the schema file, or
`GET /api/schema` on a live instance) and set the
inverse to that same string. See
[relationship-identifiers](../../infrahub-managing-schemas/rules/relationship-identifiers.md)
("The identifier is immutable once loaded") for the
full rule and the error signature.

## Related

- Downstream Python/query symptom:
  [yagni-generator-query-shape-too-broad](./yagni-generator-query-shape-too-broad.md).
  Cascade-shape findings on a generator are often a flag that this
  rule will fire on its schema too.
- Identifier and cardinality fundamentals:
  [schema-relationships](./schema-relationships.md).
