---
title: Relationship-Traversal Validation
impact: MEDIUM
tags: patterns, relationship, traversal, parent, cross-object, lifecycle
---

## Relationship-Traversal Validation

Impact: MEDIUM

To validate a node against a *related* node's state
(a child against its parent's lifecycle, a peer
against another peer), fetch the related node's
comparison attribute inside the GraphQL query via
relationship traversal, then read that nested value in
`validate()`. Treat an unresolvable related node as a
violation, not a silent skip.

### Why it matters

A check runs its `self.query` once and validates the
single result in `data`. An attribute you did not select
in the query is simply absent from `data`, so a check
that selects only the child cannot see the parent's state
from `data` at all. You *can* issue a follow-up read per
node with `self.client`, but that is O(n) round trips
that blow the check timeout on any real dataset. Pull the
comparison attribute in the same query by walking the
relationship instead.

Both sides of the relationship must be defined with
matching identifiers, or the traversal returns nothing
(see
[../../infrahub-managing-schemas/rules/relationship-identifiers.md](../../infrahub-managing-schemas/rules/relationship-identifiers.md)).

### Fetch the related node's attribute in the query

Filter the child set, then traverse into the related
node and select the attribute you will compare against
(here, a container's `status`):

```graphql
query InstallOrdering {
  DcimModule(status__value: "installed") {
    edges {
      node {
        id
        name { value }
        installed_in {
          node {
            container {
              node { id name { value } status { value } }
            }
          }
        }
      }
    }
  }
}
```

The nested `container { node { status { value } } }`
is the whole point: without it, `validate()` has no
parent status to test.

### Read the nested value and flag the mismatch

Unwrap defensively — a relationship can be null — and
surface an unresolvable parent as its own error rather
than skipping it, so a broken link cannot pass silently:

```python
ALLOWED_CONTAINER_STATUS = {"installed", "maintenance"}


class DcimInstallOrderingCheck(InfrahubCheck):
    query = "dcim_install_ordering"

    def validate(self, data: dict) -> None:
        for edge in data["DcimModule"]["edges"]:
            node = edge["node"]
            bay = (node.get("installed_in") or {}).get("node")
            container = ((bay or {}).get("container") or {}).get("node")
            name = node["name"]["value"]
            if container is None:
                self.log_error(
                    message=f"{name} is 'installed' but has no resolvable container",
                    object_id=node["id"],
                    object_type="DcimModule",
                )
                continue
            status = (container.get("status") or {}).get("value")
            if status not in ALLOWED_CONTAINER_STATUS:
                self.log_error(
                    message=(
                        f"{name} is 'installed' but its container "
                        f"{container['name']['value']} is '{status}'"
                    ),
                    object_id=node["id"],
                    object_type="DcimModule",
                )
```

### Exempt the root of the chain

The top of a containment hierarchy has no parent (a
chassis is installed into nothing), so exempt it rather
than flagging it as "no resolvable container". Scope the
query to the kinds that *have* a parent, or branch on
kind in `validate()`.

### Common mistakes

- Querying only the child and discovering in `validate()`
  that the parent's status was never fetched.
- Skipping a node whose relationship is null instead of
  flagging it — a dangling link then merges unnoticed.
- Assuming every nested `node` is present; each hop
  (`installed_in`, `container`) can be null and needs an
  `or {}` guard before the next `.get`.

Reference: [patterns-common.md](./patterns-common.md)
for error-collection and performance bucketing, and
[examples.md](../examples.md) for complete checks.
