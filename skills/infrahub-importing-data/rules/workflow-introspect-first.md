---
title: Introspect the Schema Before Mapping
impact: CRITICAL
description: >-
  Discover the schema read-only via MCP → infrahubctl schema export →
  /api/schema REST → local schemas/*.yml, stop at the first source that
  returns the kinds the CSV needs, never propose a schema edit.
tags: workflow, schema, introspection, mcp, infrahubctl, api, fallback
---

## Introspect the Schema Before Mapping

Impact: CRITICAL

Read the schema first, write nothing. Walk a fixed
priority chain — **MCP → `infrahubctl` → REST API →
local `schemas/*.yml`** — and stop at the first source
that returns the kinds the CSV needs. The schema is
**read-only** throughout the import; this skill never
proposes a schema edit.

### Why it matters

Every mapping decision — column-to-attribute,
label-vs-name, scalar-vs-list reference — depends on
what the schema actually declares on the target
branch. Guessing produces load-time rejections that
surface deep in the workflow, often after files are
already on disk.

Each source has a different freshness vs. availability
trade-off:

| Source | Freshness | Available when | Notes |
| ------ | --------- | -------------- | ----- |
| MCP server | live, branch-aware | The `infrahub` MCP server is configured in the session | Same surface `infrahub-analyzing-data` uses |
| `infrahubctl schema export` | live, branch-aware | A reachable server + `infrahubctl` configured | CLI export against the configured server |
| `/api/schema` REST | live, branch-aware | The server is reachable but `infrahubctl` is not configured locally | Plain HTTP; useful in CI / containers |
| Local `schemas/*.yml` | may lag deployed state | No server reachable at all | Last resort; step 11 server validate catches divergence |

### How to introspect

Try in order; stop at the first source that returns
all the kinds you need.

1. **MCP (preferred).** Use the same query surface
   `infrahub-analyzing-data` uses. Fetch the target
   kinds, their attributes, dropdown choices,
   relationship peers, and HFIDs. See
   [../../infrahub-analyzing-data/rules/mcp-tools.md](../../infrahub-analyzing-data/rules/mcp-tools.md).

2. **`infrahubctl schema export`.** Export the
   deployed schema for the target branch to a local
   directory and read it like the on-disk fallback,
   but with live values:

   ```bash
   infrahubctl schema export --branch <name> ./.schema-export
   ```

3. **REST `/api/schema`.** Direct HTTP fetch when
   `infrahubctl` is unavailable (e.g., CI, a
   different server than the configured one):

   ```bash
   curl -s "$INFRAHUB_ADDRESS/api/schema?branch=<name>" \
     | jq '.nodes[] | select(.name == "<Kind>")'
   ```

4. **Local `schemas/*.yml`** in the repo. Read every
   schema YAML in the working tree. Resolve
   `inherit_from` chains. Note which kinds carry
   HFIDs and which relationship blocks declare
   component/parent identifier pairs. Step 11 server
   validate is required after emission because the
   on-disk schema may lag the deployed branch.

5. **Never propose a schema edit.** If the schema
   is missing a feature the CSV requires, escalate
   to [../../infrahub-managing-schemas/SKILL.md](../../infrahub-managing-schemas/SKILL.md)
   — that's a separate manual decision. See
   [workflow-fail-closed-on-unmapped-columns.md](./workflow-fail-closed-on-unmapped-columns.md).

### Common mistakes

- **Skipping introspection because MCP isn't
  connected.** Walk the chain — `infrahubctl schema
  export`, then `/api/schema`, then local files.
  Telling the user "the schema is unreachable,
  here's a guess" is the wrong failure mode.
- **Stopping at the on-disk schema when a server
  is reachable.** The on-disk copy may lag deployed
  state. Prefer MCP / `infrahubctl` / API whenever
  one of them works.
- **Trusting an attribute lookup against a stale
  `schemas/*.yml`.** When a live source is
  unavailable, plan to re-run `infrahubctl object
  validate` after emission to catch divergence.
- **Inferring HFID order.** Read it from the
  schema, never guess. The HFID order is a
  positional lookup at load time and reversing two
  elements still parses but resolves to the wrong
  row.

Reference: [Infrahub Docs](https://docs.infrahub.app)
