---
title: Response-Driven Hydration via InfrahubNode.from_graphql
impact: HIGH
tags: from_graphql, hydration, refactor, detection, round-trips
---

## Response-Driven Hydration via `InfrahubNode.from_graphql`

Impact: HIGH

`InfrahubNode.from_graphql(client, branch, data)` hydrates a
typed `InfrahubNode` directly from a GraphQL response payload,
avoiding a second `client.get()` round trip per peer. A
generator that iterates `N` peers from the cascade query and
re-fetches each one issues `N + 1` round trips; the same
generator using `from_graphql` issues `1`.

This rule is **detection-focused**: it tells you how to find
generators that should adopt the pattern, what query coverage
is required, and how to apply the refactor mechanically.

### Why it matters

Generators run on every proposed change touching the target
group and again after merge. For wide fan-out designs (a
topology with dozens of devices, a segment touching every
leaf), the `N + 1` cost compounds quickly — both in wall-clock
time and in pressure on the GraphQL endpoint. The fetched
payload already contains everything the typed peer needs;
re-fetching is purely wasted work.

The pattern is also clearer at the call site: the loop body
operates on a typed `InfrahubNode`, not on raw
`edge["node"][<attr>]["value"]` dictionary access.

### Decision tree — should this generator use `from_graphql`?

Apply in order:

1. **Does `generate()` iterate `data[<Kind>]["edges"]` or
   nested `…["edges"][0]["node"][<rel>]["edges"]`?**
   - YES → continue to (2)
   - NO → `from_graphql` doesn't apply. The generator likely
     creates new nodes via `client.create()` or fetches via
     `client.filters()` — both are valid patterns, not refactor
     candidates.

2. **Inside the loop, does the code call
   `self.client.get(kind=…, hfid=…)` or `(kind=…, id=…)` on
   the peer it just iterated?**
   - YES → **strong refactor candidate**. The `client.get` is
     a wasted round trip; the peer's data is already in
     `data`.
   - NO → check (3).

3. **Does the loop body only set 1–2 attributes and call
   `.save()`?**
   - YES → still a candidate, but verify the response payload
     has enough fields for the `from_graphql` constructor
     (must include `__typename` — see "Query coverage" below).
   - NO → if the loop navigates deeper relationships on the
     typed node or computes derived properties, `client.get()`
     gives full hydration that may be required. Refactor with
     caution and verify the deeper rels are present in the
     payload.

### Detection heuristic (grep)

Run from the repo root:

```bash
# Outer loops over response edges
grep -nE 'for [a-z_]+ in data\["[^"]+"\]\["edges"\]' \
  generators/*.py

# Peer re-fetches by hfid/id inside the same files
grep -nE 'self\.client\.get\(kind=["\047][^"\047]+["\047],\s*(hfid|id)=' \
  generators/*.py
```

A file that hits BOTH greps in the same function is a strong
refactor candidate. Cross-check against the decision tree
above.

### Query coverage requirements

For `from_graphql` to construct the typed node correctly, the
GraphQL response for each iterated edge MUST include:

1. **`__typename`** — required to resolve the kind when no
   `schema=` argument is passed. Add it under the inline
   fragment or as a sibling of `id`/`hfid`:

   ```graphql
   bgp_neighbors {
     edges { node {
       id
       hfid
       __typename
       drained { value }
     }}
   }
   ```

2. **`id`** — required for upsert mutations (identifies the
   node).
3. **Every attribute the generator will MUTATE** — the
   attribute-state machinery compares current values to
   classify the save as a no-op vs. a change. A missing
   current value forces every save into the "change" path even
   when the value is identical.
4. **(Recommended)** every attribute the generator READS for
   downstream branching — otherwise the typed node sees
   `value=None` for those fields.

Unfetched optional one-cardinality relationships are preserved
on save by the SDK's partial-hydration handling, but explicit
query coverage is still good practice for clarity and
future-proofing.

### Refactor recipe

**Before** (one `client.get()` round trip per peer):

```python
async def generate(self, data: dict) -> None:
    edges = data[KIND]["edges"][0]["node"][REL]["edges"]
    for edge in edges:
        peer_hfid = edge["node"]["hfid"]
        peer = await self.client.get(
            kind=PEER_KIND, hfid=peer_hfid,
        )
        peer.<attr>.value = <new_value>
        await peer.save(allow_upsert=True)
```

**After** (zero re-fetches; hydrated from response):

```python
from infrahub_sdk.node import InfrahubNode


async def generate(self, data: dict) -> None:
    edges = data[KIND]["edges"][0]["node"][REL]["edges"]
    for edge in edges:
        peer = await InfrahubNode.from_graphql(
            client=self.client,
            branch=self.branch,
            data=edge,
        )
        peer.<attr>.value = <new_value>
        await peer.save(allow_upsert=True)
```

**Query change** — add `__typename` to each iterated peer's
node selection:

```diff
 bgp_neighbors {
   edges { node {
     id
     hfid
+    __typename
     drained { value }
   }}
 }
```

### When NOT to refactor

- **Generator creates new nodes via `client.create()`** —
  `from_graphql` needs an existing node payload, not a
  creation contract.
- **Generator uses `client.filters()` for runtime-discovered
  peers** — `filters()` already returns typed nodes; no
  re-fetch involved.
- **Generator navigates deep relationship chains on the typed
  node** — if the loop body does
  `peer.local_interface.peer.device.peer.<attr>`, the partial
  hydration may not include the deeper rels and navigation
  triggers extra round trips anyway. `client.get()` with an
  explicit `include=[…]` may be more readable.
- **The query payload is intentionally trimmed for size
  reasons** (large fan-out). The `client.get()` round trip per
  peer may be cheaper than including every attribute on every
  edge in the original query.

### Relationship to `convert_query_response`

When `convert_query_response: true` is set in `.infrahub.yml`,
the SDK pre-hydrates the entire response into `self.nodes` for
the generator's primary kind. That is the right tool when the
generator works with the primary target's typed form. Use
`from_graphql` instead when iterating a *nested relationship*
inside the response — `self.nodes` doesn't cover nested peers
transitively.

### Reference

- SDK source: `infrahub_sdk/node/node.py` —
  `InfrahubNode.from_graphql` (async classmethod;
  `from_graphql(client, branch, data, schema=None, timeout=None)`).
  Accepts either the edge dict (`{"node": {…, "__typename": …}}`)
  or the unwrapped node dict — both are checked for
  `__typename`.
- Canonical example in the OpsMill demos:
  `infrahub-demo-service-catalog/generators/implement_dedicated_internet.py`
  (uses `from_graphql` to hydrate the primary service node from
  the cascade query; demonstrates the same constructor call
  shape as this rule's recipe).
- See [examples.md](../examples.md) §5 for a complete
  before/after refactor with verification steps.
