# Infrahub Marketplace Reference

The [Infrahub Marketplace](https://marketplace.infrahub.app/) publishes
maintained, versioned **schemas** for reuse. Before modelling *any*
domain from scratch, search the whole marketplace — if a published
schema already covers it, reuse it and skip the modelling entirely.

This is the single source of truth for reusable schemas. Reuse **only**
from the marketplace; do not copy schema YAML out of GitHub
repositories (that loses the versioning and update path).

## What it hosts

- **Schemas** — individual published schemas, addressed as
  `namespace/name` (e.g. `infrahub/vlan-translation`).
- **Collections** — bundles of related schemas, addressed the same
  `namespace/name` way (e.g. `infrahub/routing-bgp`,
  `infrahub/base-schemas`, `infrahub/security-mgmt`). Pull a collection
  when you need a whole related stack (all of routing, a base set)
  rather than one schema at a time.

The marketplace is schema-focused — it does not host generators,
transforms, checks, or menus. Those remain defined in your own
repository, but they can target and extend schemas you pulled from the
marketplace.

## Fetching (infrahubctl first)

Prefer `infrahubctl` wherever it exposes the capability. The CLI is the
fetch path:

```bash
infrahubctl marketplace get <namespace>/<name>
```

Flags:

- `-v, --version` — pin a specific version (default: latest published)
- `-c, --collection` — force the collection path when an identifier
  exists as both a schema and a collection (otherwise auto-detected)
- `-s, --stdout` — print to stdout instead of writing files
- `-o, --output-dir` — where downloaded files are saved (default:
  `schemas`)
- `--marketplace-url` — override the marketplace base URL (see Airgap)

After fetching, `inherit_from` the pulled generics and add only your
genuinely new, site-specific attributes on top.

## Discovery / search (infrahubctl)

`infrahubctl marketplace` browses the catalog directly — you do not need
to know an identifier up front. Each command pages through the *entire*
catalog by default (no manual pagination) and takes `--json` for
scripting:

```bash
infrahubctl marketplace list                    # every published schema
infrahubctl marketplace list --collections      # every published collection
infrahubctl marketplace search <term>           # match name / display name / description
infrahubctl marketplace show <namespace>/<name> # versions, members, dependencies
```

Flags shared by `list` / `search`:

- `-l, --limit` — cap the results (otherwise every page is returned)
- `--collections` — target collections instead of schemas
- `--json` — raw JSON on stdout; status notes go to stderr, so it pipes
  cleanly

Pick an identifier from the results, then fetch it with
`infrahubctl marketplace get <namespace>/<name>` (see above). The
web catalog at <https://marketplace.infrahub.app/> is a browsable
alternative when you'd rather click than type.

## Airgap / offline environments

An unreachable marketplace is a fallback path, not a failure:

1. Point `--marketplace-url` (or the `INFRAHUB_MARKETPLACE_URL` env var)
   at an internal marketplace mirror. Every `marketplace` subcommand
   (`list` / `search` / `show` / `get`) honors it, so full-catalog
   browsing and fetching work offline.
2. If no mirror is reachable, proceed with a custom schema — still
   preferring built-in primitives. Never block schema work on
   marketplace reachability.
