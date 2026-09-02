---
title: Path Traversal and How to Constrain It
impact: HIGH
tags: patterns, traversal, traverse_paths, path_exists, graph
---

## Path Traversal and How to Constrain It

Impact: HIGH

Use the SDK's `traverse_paths` rather than hand-rolling
a graph walk. Constrain it by **relationship identifier
plus a depth bound**, not by kind: kind filtering
restricts which *nodes* may appear, not which *edges*
are followed.

### Why it matters

Reaching for the platform's traversal instead of a
bespoke walker is the choice the rest of this skill
pushes toward, and it is the right one: the walk runs
server-side in one query rather than N round trips per
hop.

The failure is that the traversal returns
**successfully** and the results look structurally
valid. A shared low-cardinality reference object — a
device type, a status, a catalog entry that many objects
point at — becomes a shortcut joining two otherwise
unrelated parts of the graph, so you get routes with no
physical meaning. Nothing errors. A wrong result is not
distinguishable from a right one by shape, so it is
carried forward until something checks it against
known-good expectations.

The parameter names invite the mistake, which is the
part worth memorising:

| Parameter | What it actually does |
| --------- | --------------------- |
| `kind_filter` | **Whitelist.** Only traverse through nodes of these kinds |
| `included_kinds` | **Not a whitelist.** Re-includes kinds that are excluded *by default*. No effect on anything you passed in `excluded_kinds` in the same request |
| `excluded_kinds` | Unioned with the defaults (`BuiltinIPNamespace` and its implementers) |
| `excluded_namespaces` | Unioned with the defaults `Core, Internal, Builtin, Lineage, Profile, Template`. **The defaults cannot be opted out of** |
| `relationship_filter` | Only follow these **schema relationship identifiers** |

`included_kinds` is the one that reads like the
whitelist and is not. And note that even `kind_filter`
constrains nodes: a shared catalog node of an allowed
kind still bridges unrelated subgraphs.

### The working pattern

Constrain by relationship identifier and bound the
depth:

```python
from infrahub_sdk.exceptions import VersionNotSupportedError


class RouteBuilder(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        service = data["NetService"]["edges"][0]["node"]

        result = await self.client.traverse_paths(
            source=service["endpoint_a"]["node"]["id"],
            destination=service["endpoint_z"]["node"]["id"],
            # Identifiers, not relationship names. This is the constraint
            # that actually stops the walk crossing a shared catalog node.
            relationship_filter=[
                "netendpoint__netsegment",
                "netsegment__netendpoint",
            ],
            max_depth=6,
            shortest_paths_only=False,
            branch=self.branch_name,
        )

        if result.truncated_at_depth is not None:
            # The search ran out of budget. Paths are complete only BELOW
            # this depth, so acting on them now would silently under-report.
            raise ValueError(
                f"traversal truncated at depth {result.truncated_at_depth}; "
                "raise max_depth or narrow relationship_filter"
            )

        for path in result.paths:
            ...
```

### `relationship_filter` takes identifiers, not names

This is the most common way to get an empty result and
conclude the traversal is broken:

```python
relationship_filter=["interfaces"]              # WRONG: a relationship NAME
relationship_filter=["dcimdevice__dcimendpoint"]  # RIGHT: a schema identifier
```

The identifier is the `identifier:` on the relationship
in the schema, shared by both sides. The per-side names
that appear in the *result* are not accepted as input.

### Defaults that bound the answer

| Parameter | Default | Ceiling |
| --------- | ------- | ------- |
| `max_depth` | 5 | 30 |
| `max_paths` | 10 | 100 |
| `shortest_paths_only` | **true** | — |

`shortest_paths_only: true` returns only the shortest
path through each intermediate object. It is fast and it
**silently drops longer routes through the same
objects**, which is usually not what a route-discovery
generator wants. Set it `False` for exhaustive mode and
accept the cost.

### Two signals in the result

- **`truncated_at_depth`** — `None` when the search
  completed. Otherwise the depth at which it ran out of
  budget: the returned paths are complete only for
  depths below that value, and deeper paths may exist.
  **Check this before acting on the result.** It is the
  one shape-level signal that the answer is incomplete.
- **`excluded_kinds`** — what was actually excluded, the
  defaults plus your additions minus your re-inclusions.
  Read it when a path you expected is missing.

### Just asking whether a path exists

`path_exists` requests a single path, which is the
cheapest way to answer the question. It takes the same
source, destination and filter arguments:

```python
if not await self.client.path_exists(
    source=a_id, destination=z_id,
    relationship_filter=["netendpoint__netsegment"], max_depth=6,
):
    self.log.warning("no route between the endpoints; skipping")
    return
```

### Validate against a known-good result first

Because a wrong traversal is shaped exactly like a right
one, pin one expected route set before depending on the
walk:

```python
EXPECTED = {("endpoint-a", "segment-1", "endpoint-z")}
# A hop carries `node` and `relationship`; the label lives on the node.
assert {tuple(h.node.display_label for h in p.hops) for p in result.paths} == EXPECTED
```

Do this once, in a test, against a fixture graph. It is
the only way to tell the shortcut-through-a-catalog-node
failure from a correct answer.

### Version floor

Path traversal requires **Infrahub 1.10 or later**. The
SDK raises `VersionNotSupportedError` against an older
server rather than returning an empty result, so catch
it if the generator has to run against mixed versions.

### Common mistakes

- Reaching for `included_kinds` as the whitelist. It
  re-includes default exclusions only.
- Passing relationship *names* to
  `relationship_filter`.
- Leaving `shortest_paths_only` at its default while
  expecting every route.
- Ignoring `truncated_at_depth` and treating a truncated
  result as complete.
- Filtering by kind and expecting it to stop the walk
  crossing a shared reference object. It will not: use
  `relationship_filter`.
- Hand-rolling the walk with per-hop queries. Slower,
  and it re-implements the exclusions.

Reference:
[api-reference.md](api-reference.md),
[patterns-common.md](patterns-common.md)
