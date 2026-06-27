---
title: yagni-generator-query-shape-too-broad
impact: MEDIUM
ladder_step: 4
tags: audit, yagni, generator, query-shape, cross-references
---

# Rule: yagni-generator-query-shape-too-broad

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 4 — Can an indirect relationship traversal answer it?

## What It Checks

Generator queries whose shape fetches more than the generator
actually needs to act on, typically as a workaround for a missing
schema inverse or a conflation between the trigger contract and the
data contract. Three patterns:

1. The generator's trigger group (`CoreGeneratorGroup`) appears
   inside its data query — the membership that dispatched the
   generator is being re-fetched as data.
2. The generator's Python contains a focal-exclude loop:
   `for X in data[Kind][edges]: if X.attr.value == focal.attr.value: continue` —
   the signature of "fetched the whole collection just to drop one
   row".
3. The generator's `.gql` has three or more top-level kind sections
   that could collapse to one traversal if the schema declared the
   right inverse.

## Why it matters

A generator that pulls its own `CoreGeneratorGroup` membership inside
the data query is asking the platform to compute, on every dispatch,
the very fact that just triggered it. The cost compounds: for `M`
triggered nodes the query returns an `M × N` matrix where the `M`
axis is already known. More importantly it signals a design
conflation — the author has not separated "who dispatched me" from
"what data do I need" — and the rest of the generator usually
inherits that confusion (focal-exclude loops in Python, extra
top-level sections that re-anchor the same data through a different
starting node).

The focal-exclude pattern is the runtime fingerprint of that
conflation. It fetches an entire collection over the wire just to
discard one row and act on the rest. In the worst case it turns an
`O(1)` lookup into an `O(N)` query plus an `O(N)` Python filter, and
it scales with the size of the collection rather than the size of
the work the generator actually does.

Catching this at audit time is the only realistic checkpoint: the
generator runs correctly, the proposed-change pipeline reports
success, and the query cost only shows up as latency under fan-out.
By the time it surfaces in production the refactor is invasive —
both the `.gql` and the Python need to change together.

## Checks

1. **No `CoreGeneratorGroup` in the data query**: the generator's
   `.gql` file (resolved via the generator's `query` class attribute
   → the matching `queries` entry in `.infrahub.yml` → its
   `file_path`) must not name `CoreGeneratorGroup` as a top-level
   field or as a nested traversal target. The trigger group belongs
   only in `.infrahub.yml` `targets:`.
2. **No focal-exclude loops in the generator's Python**: scan the
   generator file for an outer loop over `data[<Kind>]["edges"]` (or
   a `.get` chain equivalent) whose body's first conditional
   compares an attribute on the loop variable to the same attribute
   on `focal` / `self.focal` and immediately `continue`s.
3. **Top-level kind sections — review when >2**: count the top-level
   fields under the `query` root in the generator's `.gql`. Two or
   fewer is normal (the focal kind plus one related anchor). Three
   or more is not automatically wrong, but warrants a review
   finding: "Could one of these sections be reached by walking a
   relationship from another section? If yes, the schema is missing
   an inverse and the query is paying for it." Cross-reference
   [yagni-missing-inverse-forces-python-filter](./yagni-missing-inverse-forces-python-filter.md)
   when the answer is yes.

## What NOT to flag

- Generators whose three top-level sections are genuinely unrelated
  kinds (no traversal path could collapse them). Review prompt fires
  but the answer is "no, this is correct shape."
- Generators that intentionally fetch the focal's siblings to
  compute a position-dependent value (rank within group, neighbour
  count) — that's an aggregate, not a filter-and-discard.
- Generators where the `CoreGeneratorGroup` appears only inside a
  fragment used by other queries and the inclusion is incidental
  (rare; verify before suppressing).

## Common Issues

- `CoreGeneratorGroup(name__value: "pop_designs")` appears as a
  top-level field in the generator's data query — should be removed;
  trigger membership is already implicit in dispatch.
- Outer loop `for design in data["TopologyPopDesign"]["edges"]:`
  immediately followed by
  `if design["node"]["name"]["value"] == self.focal.name.value: continue`
  — the entire collection is being fetched to skip one row.
- Three or more unrelated top-level kind sections in the same `.gql`
  — often a sign that one section's anchor could traverse to the
  others, but the inverse relationship doesn't exist on the schema
  so the author re-anchored via a separate query root.

## Related

- Schema-side cause:
  [yagni-missing-inverse-forces-python-filter](./yagni-missing-inverse-forces-python-filter.md).
  Cascade-shape findings on a generator are often a flag that the
  missing-inverse rule will fire on its schema too.
- `from_graphql` adoption for N+1 round trips inside the generator is
  a separate but adjacent concern. See
  [patterns-hydration](../../infrahub-managing-generators/rules/patterns-hydration.md)
  in the generators skill. A generator hitting this rule frequently
  benefits from that one too — re-check both together.
