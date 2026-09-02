---
title: yagni-reuse-existing-marketplace-schema
impact: MEDIUM
ladder_step: 1
tags: audit, yagni, schema, marketplace, reuse
---

# Rule: yagni-reuse-existing-marketplace-schema

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 1 — Does an off-the-shelf schema already exist?

## What It Checks

A schema file that hand-rolls a domain the Infrahub Marketplace
(<https://marketplace.infrahub.app/>) already publishes — defining the
domain's core nodes from scratch with **no** `infrahubctl marketplace
get` provenance and **no** `inherit_from` of a marketplace-published
generic.

Detection is an **offline signature heuristic**: it matches the repo's
local schema files against the static table of common
marketplace-published domains below. It deliberately does *not* call the
marketplace, so an audit produces identical results on any machine,
online or airgapped. The trade-off is that it only catches the domains
in this table — the broader "search the whole marketplace before
modelling anything" discipline is authoring guidance, applied when
schemas are written (managing-schemas workflow step 2), not at audit
time.

Common marketplace-published domains (the audit-time signature set):

| Domain | Signature nodes/attributes |
| ------ | -------------------------- |
| DCIM | Device, Interface, Rack, Platform, DeviceType |
| Location | Continent, Country, Region, Site, Building, Floor |
| Organization / tenancy | Organization, Provider, Manufacturer, Tenant |
| Circuits | Circuit, CircuitEndpoint, Provider |
| Cabling | Cable, Connector |

IPAM (IP address / prefix / namespace) and VLANs are **not** this
rule's concern — `yagni-custom-domain-primitives-instead-of-builtin`
(step 2) owns them.

## Why it matters

Reuse is the cheapest outcome on the cost-to-fix ladder — it beats
every "cheaper layer" below it. A maintained marketplace schema ships
the domain's relationships, display config, hierarchies, and downstream
integrations already worked out and version-tracked. Hand-rolling the
same domain re-derives all of that, then diverges from the platform's
evolving model — every future marketplace improvement becomes a manual
port, and the initial "quick" schema quietly accretes the exact
attributes and relationships the published schema already had.

The fix is cheapest before data is loaded: adopting the marketplace
schema after objects exist forces a migration.

## The fix

Reuse the published schema instead of redefining it: pull it with
`infrahubctl marketplace get <namespace>/<name>`, then `inherit_from`
the pulled generics and add only genuinely new, site-specific
attributes. Reuse still leaves the site-specific modelling to do — it
replaces re-deriving the domain's core, not every schema decision.

Discovery (`list` / `search` / `show`), CLI flags, collections, and the
airgap fallback (`--marketplace-url` internal mirror) are documented
once in
[../../infrahub-common/marketplace-reference.md](../../infrahub-common/marketplace-reference.md)
— consult it rather than re-deriving usage here. Two constants worth
repeating: reuse only from the marketplace (never a GitHub checkout),
and an unreachable marketplace is a fallback path (mirror, then custom
schema), never a reason to block schema work.

## What the recommendation must not oversimplify

Two things make a naive "adopt the published schema"
finding wrong, and both were reported from the field.

**A published file is not atomic.** It can define
several generics with very different dependency costs.
Judging the file as a unit lets one expensive generic
veto every cheap one in it, and the observed outcome was
the reverse of this rule's intent: reuse was rejected on
the strength of a generic that dragged in a competing
device hierarchy, and the shape was modelled from
scratch instead. So the finding should name **which
generic or node to adopt**, not just the file, and the
cost of a candidate is its transitive peer set rather
than its line count. See
[../../infrahub-managing-schemas/rules/reuse-evaluate-per-generic.md](../../infrahub-managing-schemas/rules/reuse-evaluate-per-generic.md).

**A marketplace kind is a carried dependency, not a
platform guarantee.** Adopting it means the repository
must fetch and commit the published files and load them
before its own schema, or the result loads on the
author's machine and fails on a clean instance. That is
still usually the right trade, but it is a trade, and
the finding should say so rather than presenting reuse
as free. There is no location kind in the platform core,
which is the most common place this assumption breaks.
See
[../../infrahub-managing-schemas/rules/reuse-verify-kind-availability.md](../../infrahub-managing-schemas/rules/reuse-verify-kind-availability.md).

## Checks

1. A schema defines ≥2 signature nodes of a marketplace-published
   domain from the table above (e.g. `Device` + `Interface`, or
   `Region` + `Site`) with no `infrahubctl marketplace get` provenance
   and no `inherit_from` referencing a marketplace-published generic
   anywhere in the file.
2. A custom domain node duplicating a published schema's node
   (name + ≥3 of the same attribute names) without inheritance.

## What NOT to flag

- Schemas pulled via `infrahubctl marketplace get` and extended with
  `inherit_from` (the pattern we want) — even if they add many custom
  attributes.
- Domains outside the signature table above — the offline heuristic has
  no signature for them, so it stays silent rather than guessing.
- A single incidental node that happens to share a name (e.g. one
  `Site` node in an otherwise unrelated schema) — the rule needs a
  domain footprint (≥2 signature nodes), not a name collision.
- IPAM / VLAN primitives — owned by
  `yagni-custom-domain-primitives-instead-of-builtin`.
- Airgapped repos that pull from an internal marketplace mirror via
  `--marketplace-url` — that IS marketplace reuse.
- A repo that adopted part of a published file and recorded provenance
  (identifier, version, what was taken, why the rest was excluded).
  Vendoring a subset deliberately is reuse, not hand-rolling.

## Common Issues

- A `schemas/dcim.yml` defining `Device`, `Interface`, `Rack` from
  scratch. Replace with `infrahubctl marketplace get` of the DCIM
  schema and `inherit_from` its generics; keep only site-specific
  attributes.
- A bespoke `Site` / `Region` / `Country` location tree that
  re-implements a marketplace-published location schema. Pull it with
  `infrahubctl marketplace get` instead.
- An `Organization` + `Provider` + `Tenant` model duplicating the
  marketplace organization schema.
