---
title: Evaluate a Published File Per Generic, Not as a Unit
impact: HIGH
tags: reuse, marketplace, generics, dependencies, provenance
---

## Evaluate a Published File Per Generic, Not as a Unit

Impact: HIGH

A published schema file is not atomic. Evaluate each
generic and node in it separately. The cost of a
candidate is its transitive peer set, not the file's line
count.

### Why it matters

Published files routinely define several shapes with
very different dependency costs. Judge the file as a
unit and one expensive shape vetoes every cheap one in
it, so reuse gets rejected for a reason that does not
apply to the part actually needed, and a published shape
gets reinvented.

That failure is quiet and expensive: nothing errors, the
hand-rolled model works, and nobody discovers that the
platform already published the shape. In the reported
case a sixty-line file defined two generics. One dragged
in a competing device and interface hierarchy. The other
peered a single built-in kind and cost nothing. The file
was rejected on the strength of the expensive one and
the shape was modelled from scratch. Taking only the
cheap generic worked and loaded first time.

### How to evaluate

For each generic or node in the file, separately:

1. **List its peers.** Every `peer:` on a relationship,
   plus every kind in `inherit_from`, `parent`,
   `children`, and `menu_placement`.
2. **Classify each peer:**

   | Class | Cost |
   | ----- | ---- |
   | Platform core (`Core*`, `Builtin*`, `Ipam*`) | none |
   | Already present in your repository | none |
   | A new transitive dependency | the whole set it drags in, recursively |

3. **Recurse.** A new peer's own peers count too. This is
   where a cheap-looking candidate turns expensive.
4. **Decide per candidate.** A sibling with expensive
   peers is **not** a reason to reject a cheap candidate
   in the same file.

Confirm the tier of every peer with
[reuse-verify-kind-availability.md](reuse-verify-kind-availability.md)
before calling it free.

### Prefer the whole file when the cost is comparable

Taking the file whole keeps the update path: a later
`infrahubctl marketplace get` refreshes it. Taking a
subset breaks that, so only do it when the excluded part
carries a dependency you genuinely do not want.

### When you take a subset, record provenance

A partial copy with no provenance is indistinguishable
from something hand-written, so nobody can later tell
whether it has drifted from upstream or been
deliberately changed. Record it in the file itself:

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

# Vendored from marketplace `infrahub/optical-transport`, version 1.4.0,
# fetched 2026-08-31 with:
#   infrahubctl marketplace get infrahub/optical-transport -v 1.4.0
#
# Taken: the OpticalEndpoint generic only.
# Excluded: the TransportDevice generic, whose `chassis` and `linecard`
#   peers pull in a second device/interface hierarchy that competes with
#   the DcimDevice tree this repository already has.
#
# Re-check on upgrade: if upstream changes OpticalEndpoint, reconcile by
# hand. This copy is no longer refreshed by `marketplace get`.
generics:
  - name: OpticalEndpoint
    namespace: Net
    # ...
```

Four things make it useful later: the identifier, the
version, what was taken, and **why the rest was
excluded**. The last one is what stops the next reader
repeating the evaluation.

### Verify before committing to the decision

Load the candidate onto a throwaway branch before either
adopting or rejecting it:

```bash
infrahubctl branch create reuse-probe
infrahubctl schema load <dir> --branch reuse-probe
infrahubctl branch delete reuse-probe
```

A rejection based on a guess about transitive cost is
worth re-opening; one based on a failed load is not.

### Common mistakes

- Rejecting a file because its largest generic is
  expensive, without checking the others.
- Counting line count or generic count as cost.
  Transitive peers are the cost.
- Vendoring a subset with no note, so the next reader
  cannot tell it came from upstream.
- Re-modelling a shape from scratch after a unit-level
  rejection, which is the expensive outcome this rule
  exists to prevent.
- Taking a subset when the whole file would have been
  nearly free, losing the update path for nothing.

Reference:
[../../infrahub-common/marketplace-reference.md](../../infrahub-common/marketplace-reference.md)
