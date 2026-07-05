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

Before building *any* schema, the whole marketplace should be searched
for a published schema covering that domain — not just the handful
below. The marketplace publishes far more than these examples (routing,
compute, security, VLAN translation, cross-connects, and many more), so
whenever a match exists **no modelling is needed** — reuse it. The
marketplace is the single source of truth for reusable schemas; do
**not** pull schemas from GitHub repositories.

Common marketplace-published domains (illustrative only — a small slice
of the catalog; always search the whole marketplace for whatever you
are about to build):

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

1. Search the whole marketplace for the domain:
   `infrahubctl marketplace search <term>` (or `list`), and note its
   `namespace/name`.
2. Pull it: `infrahubctl marketplace get <namespace>/<name>`.
3. `inherit_from` the pulled generics, adding only genuinely new,
   site-specific attributes.

CLI flags, discovery (`list` / `search` / `show`), collections, and
the airgap fallback (`--marketplace-url` internal mirror) are
documented once in
[../../infrahub-common/marketplace-reference.md](../../infrahub-common/marketplace-reference.md)
— consult it rather than re-deriving usage here. Two constants worth
repeating: reuse only from the marketplace (never a GitHub checkout),
and an unreachable marketplace is a fallback path (mirror, then custom
schema), never a reason to block schema work.

Detection relies only on local schema files matched against the static
domain list above — no network call — so audits produce identical
results offline.

## Checks

1. A schema defines ≥2 signature nodes of a marketplace-published
   domain (e.g. `Device` + `Interface`, or `Region` + `Site`) with no
   `infrahubctl marketplace get` provenance and no `inherit_from`
   referencing a marketplace-published generic anywhere in the file.
2. A custom domain node duplicating a published schema's node
   (name + a handful of the same attributes) without inheritance.

## What NOT to flag

- Schemas pulled via `infrahubctl marketplace get` and extended with
  `inherit_from` (the pattern we want) — even if they add many custom
  attributes.
- Genuinely novel domains with no marketplace equivalent (search the
  whole marketplace first to be sure).
- A single incidental node that happens to share a name (e.g. one
  `Site` node in an otherwise unrelated schema) — the rule needs a
  domain footprint (≥2 signature nodes), not a name collision.
- IPAM / VLAN primitives — owned by
  `yagni-custom-domain-primitives-instead-of-builtin`.
- Airgapped repos that pull from an internal marketplace mirror via
  `--marketplace-url` — that IS marketplace reuse.

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
