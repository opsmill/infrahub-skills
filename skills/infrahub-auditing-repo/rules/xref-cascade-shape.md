---
title: xref-cascade-shape
impact: MEDIUM
tags: audit, cross-references, generators, query-shape
---

# Rule: xref-cascade-shape

**Severity**: MEDIUM
**Category**: Cross-References

## What It Checks

Validates the relationship between a generator's
trigger contract (the `CoreGeneratorGroup` declared
in `.infrahub.yml` `targets:`) and the shape of its
input GraphQL query. The trigger group should
dispatch the generator; the query should fetch the
data the generator needs to act on. Conflating the
two — fetching the trigger group itself in the data
query, or walking a whole collection in Python just
to filter down to the one focal row — produces
queries that are slower than they need to be and
harder to read than they should be.

## Why it matters

A generator that pulls its own
`CoreGeneratorGroup` membership inside the data
query is asking the platform to compute, on every
dispatch, the very fact that just triggered it.
The cost compounds: for `M` triggered nodes the
query returns an `M × N` matrix where the `M` axis
is already known. More importantly it signals a
design conflation — the author has not separated
"who dispatched me" from "what data do I need" —
and the rest of the generator usually inherits
that confusion (focal-exclude loops in Python,
extra top-level sections that re-anchor the same
data through a different starting node).

The focal-exclude pattern — `for X in
data[Kind][edges]: if X.attr.value ==
focal.attr.value: continue` — is the runtime
fingerprint of this conflation. It fetches an
entire collection over the wire just to discard
one row and act on the rest. In the worst case it
turns an `O(1)` lookup into an `O(N)` query plus
an `O(N)` Python filter, and it scales with the
size of the collection rather than the size of the
work the generator actually does.

Catching this at audit time is the only realistic
checkpoint: the generator runs correctly, the
proposed-change pipeline reports success, and the
query cost only shows up as latency under fan-out.
By the time it surfaces in production the
refactor is invasive — both the `.gql` and the
Python need to change together.

## Checks

1. **No `CoreGeneratorGroup` in the data query**:
   the generator's `.gql` file (the `file_path`
   referenced from its `generator_definitions.query`
   entry in `.infrahub.yml`) must not name
   `CoreGeneratorGroup` as a top-level field or as a
   nested traversal target. The trigger group
   belongs only in `.infrahub.yml` `targets:`.

2. **No focal-exclude loops in the generator's
   Python**: scan the generator file for an outer
   loop over `data[<Kind>]["edges"]` (or a `.get`
   chain equivalent) whose body's first
   conditional compares an attribute on the loop
   variable to the same attribute on `focal` /
   `self.focal` and immediately `continue`s. That
   is the fingerprint of "fetched the whole
   collection just to drop one row".

3. **Top-level kind sections — review when >2**:
   count the top-level fields under the `query`
   root in the generator's `.gql`. Two or fewer is
   normal (the focal kind plus one related anchor).
   Three or more is not automatically wrong, but
   warrants a review finding: "Could one of these
   sections be reached by walking a relationship
   from another section? If yes, the schema is
   missing an inverse and the query is paying for
   it." Cross-reference
   [schema-design-missing-inverses](./schema-design-missing-inverses.md)
   when the answer is yes.

## Related

- `from_graphql` adoption for N+1 round trips
  inside the generator is a separate but adjacent
  concern. See
  [patterns-hydration](../../infrahub-managing-generators/rules/patterns-hydration.md)
  in the generators skill. A generator hitting this
  rule (cascade shape) frequently hits that one
  too — flag both findings when both apply.
- Schema-side companion:
  [schema-design-missing-inverses](./schema-design-missing-inverses.md).
  Cascade-shape findings on the Python/query side
  often point at the same missing inverse the
  schema-side rule catches structurally.

## Common Issues

- `CoreGeneratorGroup(name__value: "pop_designs")`
  appears as a top-level field in the generator's
  data query — should be removed; trigger
  membership is already implicit in dispatch.
- Outer loop `for design in
  data["TopologyPopDesign"]["edges"]:` immediately
  followed by `if design["node"]["name"]["value"]
  == self.focal.name.value: continue` — the entire
  collection is being fetched to skip one row.
- Three or more unrelated top-level kind sections
  in the same `.gql` — often a sign that one
  section's anchor could traverse to the others,
  but the inverse relationship doesn't exist on
  the schema so the author re-anchored via a
  separate query root.
