---
title: yagni-denormalized-vs-indirect-relationship
impact: MEDIUM
ladder_step: 4
tags: audit, yagni, schema, relationships
---

# Rule: yagni-denormalized-vs-indirect-relationship

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 4 — Can an indirect relationship traversal answer it?

## What It Checks

Schemas that denormalize a value onto a closer node — copying an
attribute or adding a direct relationship — when the same answer is
already reachable by traversing two or three hops through existing
relationships.

## Why it matters

Denormalization without an explicit invariant creates two writeable
copies of the same fact. Either consumers query the closer copy and
silently get stale data when the source changes, or every write path
has to update both — which nothing in the schema enforces, so it
breaks the first time someone writes via a different code path. The
graph layer exists specifically so this isn't necessary; traversing
two relationships is cheap and authoritative. The data still loads
and the platform still functions, so this is an advisory MEDIUM
finding — but unchecked it accumulates into a real maintenance
liability.

## Checks

1. An attribute on node B whose value mirrors an attribute on node A
   when B is already related to A. Example: `device.site_code`
   when `device.site.code` exists.
2. A direct relationship that short-circuits an existing path. Example:
   `interface.site` added next to the existing
   `interface.device.site` traversal.
3. A relationship whose entire purpose is to surface a property of
   another related object. Example: `circuit.provider_country`
   instead of `circuit.provider.country`.
4. A schema migration that *adds* a denormalized field without a
   matching computed/derived flag or pipeline guarantee that keeps
   the values in sync.

## What NOT to flag

- Read-mostly aggregates that are too expensive to compute on every
  read (e.g., a precomputed total maintained by a generator with an
  explicit pipeline). These are valid; flag only when there's no
  evidence the value is being maintained.
- Denormalization explicitly marked as a snapshot at a point in time
  (e.g., `signed_at_address` on a contract — intentionally frozen).
- Attributes derived via `Computed` or Jinja2 — they're literally
  computed at read time, not denormalized.
- Performance-critical lookups where the path is >3 hops and the
  product team has accepted the sync burden in writing.

## Common Issues

- A `Device` node gains `region__value` when `device.location.region`
  already exists. Now updates to a region must touch every device.
- A `Circuit` node gains `provider_name__value` instead of using
  `circuit.provider.name__value`. Renaming a provider becomes a fan-
  out write.
- A relationship `circuit.region` added "for convenience" alongside
  `circuit.location.region`. Two paths, no enforced equality, no
  invariant.
