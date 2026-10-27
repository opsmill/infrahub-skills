# Migrating from NetBox — Base DCIM Differences

Infrahub's base DCIM schema overlaps in spirit
with NetBox's DCIM models, but the attribute and
field names don't always match, and crucially the
exact field set depends on which schema bundle
and which project overlays are loaded on **your**
server. This page lists the differences that bite
first when porting NetBox queries, templates, or
overlay data — and points you at the introspection
commands that tell you what your specific instance
actually exposes.

If you're not sure whether a field exists on a
node, the source of truth is the live server's
schema, not any documentation. Use:

```bash
# Dump the running schema (one YAML file per namespace)
infrahubctl schema export --branch main ./schema-export

# Or query the REST endpoint directly
curl -s "$INFRAHUB_ADDRESS/api/schema?branch=main" | jq '.nodes[] | select(.name == "Interface")'
```

GraphQL introspection on `/graphql` also works.
Five seconds of introspection beats fifteen
minutes of "Cannot query field" debugging.

## Attribute Renames and Removals

**Schemas vary between Infrahub deployments.** The
base DCIM bundle in `opsmill/infrahub` evolves
between releases, and most production projects layer
their own additions on top — so the field set on
`DcimInterface` (or any other base kind) is a moving
target. The patterns below describe recurring NetBox
↔ Infrahub differences in concept; introspect the
running schema before assuming any specific field
exists.

| NetBox concept | Infrahub equivalent (varies by schema) | Notes |
| -------------- | -------------------------------------- | ----- |
| `Interface.enabled` (Boolean) | `status` (Dropdown) and/or `enabled` (Boolean) — depends on the loaded schema | Some bundles expose only `status` (with values like `active` / `disabled` / `planned`); others expose `enabled` as a separate administrative-state flag alongside `status`; project-specific overlays can rename either. A NetBox-style query for a non-existent attribute fails with `Cannot query field 'X' on type 'DcimInterface'`. Introspect first. |
| `Interface.mode` (access/trunk enum) | `l2_mode` on a `Layer2` generic, when the L2/L3 split is modelled this way | Many schemas model L2/L3 as separate generics that interfaces inherit from rather than a single mode field. When that pattern is in use, discriminate via field presence — see [`__typename` discrimination](./graphql-queries.md#inline-fragments-populate-fields-but-__typename-returns-the-concrete-kind). |
| `Device.primary_ip4` / `primary_ip6` | depends on schema | Rarely a direct attribute. Projects model this via an explicit relationship or a computed Jinja2 attribute pulling from the interface's IP relationships. |
| `Site.tenant` (direct FK) | varies | Often wired through an extension or a tenancy module rather than as a base-DCIM attribute. |

Infrahub schemas are explicit and
project-specific. Where NetBox inherits structure
from its Django ORM, Infrahub declares every
attribute, relationship, and constraint in YAML —
the loaded bundle is what you get. The "Cannot
query field 'X'" error is the canonical signal
that your server's schema doesn't expose that
field; introspect before assuming.

## Status Values

NetBox interface and device statuses use a fixed
enum (`active`, `planned`, `staged`, `failed`,
`offline`, etc.). Infrahub status fields are
typically `Dropdown` attributes whose `choices`
are declared on the node in the schema. The set is
not standardized across all schemas — check the
schema YAML for the actual choice names, or query
`__schema` for the dropdown definition.

## Hierarchies

NetBox's `Region → Site` model is a flat
foreign-key chain. Infrahub's base location
schema uses a hierarchical generic
(`LocationGeneric` with `hierarchical: true`) and
nodes opt into it via `inherit_from`. The query
shape for traversal is `parent { node { ... } }`
and `children { edges { node { ... } } }`, not
`site.region`.

See
[../infrahub-managing-schemas/rules/hierarchy-setup.md](../infrahub-managing-schemas/rules/hierarchy-setup.md)
for the hierarchical pattern in detail.

## IPAM

NetBox uses `IPAddress.assigned_object` as a
generic FK to either an interface or a VM
interface. Infrahub typically models the link from
the interface side via an `ip_addresses`
relationship; the IPAM-side relationship is named
according to the schema in use.

The `IPAddress` node itself ships with `address`
(the value), not separate `address` and `family`
columns — the family is derived from the address
string.

## Groups vs. Tags

NetBox supports both `Tag` (free-form label) and
no native concept of a typed group of objects.
Infrahub provides `CoreStandardGroup` (and
specialized variants like `CoreGeneratorGroup`)
that act as typed object collections — and
artifact/generator/check pipelines target groups,
not tags. Membership is set from the member side
via `member_of_groups`, not from the group side
via inline `members:`. See
[../infrahub-managing-objects/rules/value-relationships.md](../infrahub-managing-objects/rules/value-relationships.md#group-membership-cardinality-many).

## Filter Equivalents in Queries

| NetBox query string | Infrahub GraphQL filter |
| ------------------- | ----------------------- |
| `?name__ic=spine` | `name__value__ilike: "%spine%"` (or `name__value: "spine"` for exact) |
| `?status=active` | `status__value: "active"` |
| `?site_id=4` | `site__id: "<uuid>"` |

The general shape is `<attribute>__value` for
exact match, with operator suffixes
(`__ilike`, `__regex`, etc.) appended as needed.
See
[graphql-queries.md](./graphql-queries.md) for the
full filter syntax.

## When in doubt

See the introspection commands at the top of this
file — `infrahubctl schema export` dumps the
current bundle to YAML you can grep, and the
`/api/schema` REST endpoint plus `/graphql`
introspection give the same data over HTTP. Treat
the running schema as the source of truth, not any
documentation page.
