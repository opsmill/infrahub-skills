---
title: A Generic's Implementer Set Is a Published Interface
impact: HIGH
tags: generics, inherit_from, migration, queries, blast-radius
---

## A Generic's Implementer Set Is a Published Interface

Impact: HIGH

Adding one `inherit_from` line changes the answer to
every question already being asked of that generic. The
change is invisible to `infrahubctl schema check`,
because the schema is valid before and after.

### Why it matters

Removing a kind is already recognised as a migration
hazard. **Addition is treated as free, and it is not.**
A new implementer silently changes:

- what a GraphQL query rooted on the generic returns, in
  both the set of kinds and the count
- what any pinned expectation over that generic is worth
- what any consumer summing, filtering, or iterating over
  the generic now includes
- what a `uniqueness_constraints` entry declared on the
  generic now spans, since it is enforced across every
  implementer

Nothing in the platform flags it. A schema diff that only
*adds* a kind produces **no migration and no
constraint validation**, because the new kind lands in
the added set rather than the changed set. A change to an
existing kind's `inherit_from` does trigger a migration;
a brand-new kind joining a generic does not.

In the reported case every offline gate stayed green:
`schema check` passed, the schema loaded on a branch and
on the default branch, every `.gql` file was accepted at
repository import, and the full offline unit suite
passed. The only thing that failed was an integration
test enumerating the generic against a loaded graph, and
it cost a seven-minute container run to say so. A project
without that test would have shipped it.

### Before adding a kind to a generic, enumerate the consumers

Four places, and the last is the one people forget:

1. **Queries rooted on the generic.** Grep `queries/` for
   the generic's kind.
2. **Relationships peering it.** A new implementer becomes
   a legal peer everywhere the generic is a `peer:`.
3. **Constraints declared on it.**
   `uniqueness_constraints` and `human_friendly_id` on a
   generic span every implementer, so the new kind now
   has to satisfy them and can now collide with its
   siblings. See
   [uniqueness-constraints.md](uniqueness-constraints.md).
4. **Code and tests that iterate its implementers.**
   Checks, generators, transforms, and any engine that
   sums or filters over the generic.

### Say what a new implementer means semantically

A generic peered by a relationship is often *also* a
generic that something sums or filters. Joining it for
the first reason silently opts into the second.

Concretely: if a new kind must inherit a generic because
a relationship peers it, and something else sums over
that same generic, the new kind starts being counted.
Sometimes that is the intent. When it is not, nothing
says so. Decide explicitly and write the decision down.

### Pin the set in a fast offline test

The useful distinction, and the reason this is worth a
rule rather than a warning:

| Assertion | Proves | Belongs in |
| --------- | ------ | ---------- |
| against a **loaded graph** | the *platform* returns those kinds | integration suite |
| over the **schema YAML** | the *schema declares* them | fast offline gate |

Only the second is a claim a contributor can break, and
only the second runs in under a second. Neither replaces
the other, but if you have one, have the offline one.

The test is self-contained: it reads the schema files
off disk, so it needs no fixture, no plugin and no
server.

```python
# tests/test_generic_membership.py
from pathlib import Path

import yaml

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

EXPECTED_NET_ENDPOINT_IMPLEMENTERS = {
    "NetOpticalEndpoint",
    "NetEthernetEndpoint",
    # Adding a kind here is a deliberate act. Read
    # rules/generic-membership-is-a-published-interface.md first.
}


def _declared_nodes():
    """Every node declared across the repository's schema files."""
    for path in sorted(SCHEMA_DIR.rglob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        yield from document.get("nodes") or []


def test_endpoint_implementers_are_pinned():
    actual = {
        f"{node['namespace']}{node['name']}"
        for node in _declared_nodes()
        if "NetEndpoint" in (node.get("inherit_from") or [])
    }
    added = actual - EXPECTED_NET_ENDPOINT_IMPLEMENTERS
    removed = EXPECTED_NET_ENDPOINT_IMPLEMENTERS - actual
    assert not (added or removed), (
        f"NetEndpoint implementer set changed. Added: {sorted(added)}. "
        f"Removed: {sorted(removed)}. Every query, constraint and consumer "
        "over NetEndpoint now answers differently. Update the pinned set "
        "only after checking them."
    )
```

Make the failure message list what was added and removed,
so the fix is mechanical and the reader is pointed at the
consequence rather than just at a diff.

### Common mistakes

- Treating `schema check` passing as evidence the addition
  is safe. It is valid before and after; validity was
  never the question.
- Adding the kind because a relationship demands it,
  without noticing what else reads the generic.
- Pinning the implementer set only against a live
  instance, so the gate costs a container run and cannot
  block a PR cheaply.
- Assuming the reverse: that removing a kind from a
  generic is the dangerous direction and adding one is
  not.

### Related

- [relationship-identifiers.md](relationship-identifiers.md)
  — the usual reason a kind must join a generic is that a
  relationship peers it, which is exactly when the author
  is thinking about the relationship and not about the
  generic's other consumers.
- [migration-state-absent.md](migration-state-absent.md)
  — the removal direction.
- [uniqueness-constraints.md](uniqueness-constraints.md)
  — what a constraint on the generic now spans.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
