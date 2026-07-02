---
title: yagni-reuse-existing-marketplace-schema
impact: MEDIUM
ladder_step: 1
tags: audit, yagni, schema, marketplace, reuse, schema-library
---

# Rule: yagni-reuse-existing-marketplace-schema

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 1 — Does an off-the-shelf schema already exist?

## What It Checks

A schema file that hand-rolls a *whole domain* the Infrahub
Marketplace (<https://marketplace.infrahub.app/>) or
`opsmill/schema-library` already ships — defining the domain's core
nodes from scratch with **no** `inherit_from` of a library generic and
**no** import of the library.

Marketplace-covered domains (the static catalog this rule checks
against — no network fetch):

| Domain | Signature nodes/attributes | Library source |
| ------ | -------------------------- | -------------- |
| DCIM | Device, Interface, Rack, Platform, DeviceType | `base/dcim.yml` |
| Location | Continent, Country, Region, Site, Building, Floor | `base/location.yml` |
| Organization / tenancy | Organization, Provider, Manufacturer, Tenant | `base/organization.yml` |
| Circuits | Circuit, CircuitEndpoint, Provider | `extensions/circuit` |
| Cabling | Cable, Connector | `extensions/cable` |

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
attributes and relationships the library already had.

The fix is cheapest before data is loaded: adopting the library schema
after objects exist forces a migration.

## The fix

1. Browse <https://marketplace.infrahub.app/> to find the domain's
   `namespace/name` identifier.
2. Pull it: `infrahubctl marketplace get <namespace>/<name>`
   (auto-detects schema vs. collection; `-o <dir>` sets the output
   directory, `-s` prints to stdout, `-v <version>` pins a version).
3. `inherit_from` the pulled generics and add only the genuinely new,
   site-specific attributes on top.

## Airgap / offline environments

An unreachable marketplace is a **fallback path, not a failure**. In
order:

1. Point at an internal mirror:
   `infrahubctl marketplace get <ns>/<name> --marketplace-url <url>`.
2. Use a locally-vendored `opsmill/schema-library` checkout and
   `inherit_from` its generics directly.
3. If none is reachable, proceed with the custom schema — still
   preferring built-in primitives. Never block schema creation on
   marketplace reachability.

This rule and its grader inspect only local files against the static
catalog above, so audits produce identical results offline.

## Checks

1. A schema defines ≥2 signature nodes of a catalogued domain (e.g.
   `Device` + `Interface`, or `Region` + `Site`) with no
   `inherit_from` referencing a `schema-library` / marketplace generic
   anywhere in the file.
2. No `infrahubctl marketplace get` provenance and no library import
   for a domain the catalog covers.
3. A custom domain node duplicating a library node's attribute set
   (name + a handful of the same attributes) without inheritance.

## What NOT to flag

- Schemas that already `inherit_from` a library generic (the pattern we
  want) — even if they add many custom attributes.
- Genuinely novel domains with no marketplace/library equivalent.
- A single incidental node that happens to share a name (e.g. one
  `Site` node in an otherwise unrelated schema) — the rule needs a
  domain footprint (≥2 signature nodes), not a name collision.
- IPAM / VLAN primitives — owned by
  `yagni-custom-domain-primitives-instead-of-builtin`.
- Airgapped repos that vendor `schema-library` locally and inherit from
  it — that IS reuse.

## Common Issues

- A `schemas/dcim.yml` defining `Device`, `Interface`, `Rack` from
  scratch. Replace with `infrahubctl marketplace get` of the DCIM
  schema and `inherit_from` its generics; keep only site-specific
  attributes.
- A bespoke `Site` / `Region` / `Country` location tree that
  re-implements `base/location.yml`. Pull the location schema instead.
- An `Organization` + `Provider` + `Tenant` model duplicating
  `base/organization.yml`.
