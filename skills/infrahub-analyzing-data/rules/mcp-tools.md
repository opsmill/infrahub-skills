---
title: Infrahub MCP Server Tool Reference
impact: CRITICAL
tags: mcp, tools, query, infrahub, branch, proposed-change
---

## Infrahub MCP Server Tool Reference

Impact: CRITICAL

The Infrahub MCP server exposes a set of tools that
allow Claude to interact with a live Infrahub
instance directly. Analysis and remediation
workflows depend on calling these tools correctly to
fetch, evaluate, and — when asked — change data.

The reworked server (v1.1.7) splits its surface into
**read** tools (typed queries plus raw GraphQL) and
**write** tools (typed upsert/delete, raw mutations,
and proposed-change submission). Writes are
**branch-isolated** by design: they land on an
auto-created session branch, never the default
branch, and reach the default branch only through a
Proposed Change that a human reviews and merges.

### Why it matters

MCP tools run against a live instance, so a
malformed GraphQL query comes back as "query
failed" with a partial reason — the difference
between an answer and a stack trace is the exact
shape of the kind name, the `edges`/`node` envelope,
and the attribute filter syntax. Schema discovery
via `get_schema` (or the `infrahub://schema`
resource) is the cheap first step; reaching for
`query_graphql` without it leads to round trips that
fail on a typo the introspection call would have
surfaced.

For typed reads, prefer `get_nodes` / `search_nodes`
over `query_graphql` — they return token-cheap
display labels by default and validate the kind and
filters against the schema. Reach for raw GraphQL
only when you need relationship traversal,
aggregation, or fields the typed tools don't expose.

Writes are safe by construction: `node_upsert`,
`node_delete`, and `mutate_graphql` all land on an
auto-created session branch
(`mcp/session-YYYYMMDD-<hex>`), never the default
branch. Nothing you write is visible on the source
of truth until you call `propose_changes` and a
human approves the merge — the reworked server
enforces the review loop the old
`create`/`update`-on-`main` path could bypass.

---

### Read Tools

#### `mcp__infrahub__get_nodes`

List nodes of a specific kind — the default read
path for typed queries. Prefer this over
`query_graphql` when you just need objects of one
kind.

```text
Arguments:
  kind (string, required)
    — node kind (e.g., "DcimDevice")
  filters (object, optional)
    — filter map; attribute filters use
      `<attr>__value` (e.g. {"name__value": "atl1"}),
      relationship filters chain via
      `<rel>__<attr>__value`
      (e.g. {"site__name__value": "atl1"})
  include_attributes (boolean, optional)
    — return full attribute dicts instead of
      display labels
  partial_match (boolean, optional)
    — substring instead of exact match
  limit / offset (integer, optional)
    — page large result sets; the response
      includes `total_count` and `has_more`
  branch (string, optional)
    — read from a branch (default: the default branch)
```

**Correct usage:**

```text
mcp__infrahub__get_nodes({
  "kind": "DcimDevice",
  "filters": { "role__value": "spine" },
  "include_attributes": true
})
```

Discover valid kinds via the `infrahub://schema`
resource or `get_schema`; discover valid filter keys
for a kind via `infrahub://schema/{kind}` or
`get_schema(kind="...")`.

---

#### `mcp__infrahub__search_nodes`

Find nodes of a kind by partial substring across
**all** attributes — use when you only know part of
a value. Works on concrete kinds (e.g.
`LocationSite`) and generic/abstract kinds (e.g.
`CoreNode`).

```text
Arguments:
  kind  (string, required)
  query (string, required)
    — substring to match
  limit (integer, optional)
  branch (string, optional)
```

For a filter on one specific attribute (or combining
several filters), use `get_nodes` with an explicit
`filters` dict instead.

---

#### `mcp__infrahub__get_schema`

Discover available schema kinds — call this first
when you don't know what kinds or filters exist.
Without a `kind`, returns the catalog of all kinds.
With a `kind`, returns its attributes, relationships,
and the full set of filter keys `get_nodes` accepts.

```text
Arguments:
  kind   (string, optional)
  branch (string, optional)
```

Prefer the `infrahub://schema` resource if your
client supports MCP resources; this tool returns the
same data for clients that don't.

---

#### `mcp__infrahub__query_graphql`

Execute a **read-only** GraphQL query. Mutations are
rejected at the AST level — use `mutate_graphql` for
writes. For simple attribute reads prefer
`get_nodes` / `search_nodes`; use GraphQL when you
need relationship traversal, aggregation, or fields
the typed tools don't expose.

```text
Arguments:
  query  (string, required)
    — GraphQL query string
  branch (string, optional)
    — branch to read (default: the default branch)
```

**Correct usage:**

```text
mcp__infrahub__query_graphql({
  "query": "query { DcimDevice {
    edges { node { id name { value } } }
  } }"
})
```

This tool takes no `variables` argument — inline
concrete values into the query string.

---

#### `mcp__infrahub__get_session_info`

Return the current MCP session state — call before
writes to know which branch they target. Reports the
active session branch (or `null` if no write has
happened yet) and the Infrahub address. A session
branch is lazily auto-created on the first write
(`node_upsert` / `node_delete` / `mutate_graphql`)
and named `mcp/session-YYYYMMDD-<hex>`.

```text
Arguments: none
```

---

### Write Tools

Writes never touch the default branch. The first
write of a session auto-creates a branch named
`mcp/session-YYYYMMDD-<hex>`, and every subsequent
write in the session lands there. Use
`get_session_info` to see the active branch, and
`propose_changes` to open it for human review.

#### `mcp__infrahub__node_upsert`

Create or update a node on the active session
branch. Replaces the old `infrahub_create` /
`infrahub_update` pair.

```text
Arguments:
  kind (string, required)
  data (object, required)
    — scalar attribute values only
  id   (string, optional)
    — supply to update by ID
  hfid (list of strings, optional)
    — supply to update by human-friendly ID
```

- **Create:** omit both `id` and `hfid`.
- **Update:** supply either `id` or `hfid`.

Only scalar attribute fields go in `data`. To set
relationship fields, use `mutate_graphql`.

---

#### `mcp__infrahub__node_delete`

Delete a node on the active session branch. Replaces
the old `infrahub_delete`.

```text
Arguments:
  kind (string, required)
  id   (string, optional)
  hfid (list of strings, optional)
```

---

#### `mcp__infrahub__mutate_graphql`

Execute a GraphQL mutation on the active session
branch — for complex writes the typed tools can't
express (relationship edits, bulk operations). There
is no branch override; the mutation always runs on
the session branch. Branch- and schema-management
mutations are rejected.

```text
Arguments:
  query (string, required)
    — GraphQL mutation string
```

---

#### `mcp__infrahub__propose_changes`

Open a Proposed Change (like a pull request) from
the active session branch to the default branch, so
a human can review, approve, and merge the session's
changes. The session branch stays active after
calling — you can keep making changes.

```text
Arguments:
  title (string, required)
  description (string, optional)
  destination_branch (string, optional)
    — defaults to the instance default branch
```

Call this once your writes are ready. Until a human
merges it, nothing you wrote is visible on the
default branch.

---

#### `mcp__infrahub__reset_session_branch`

Reset or switch the active session branch. With no
`branch`, clears the cached session branch so the
next write auto-creates a fresh one (use after your
work has merged and you want a new change set). With
a `branch`, points the session at that named branch
(created if the name matches the configured branch
pattern; the default branch and merged/read-only
branches are rejected).

```text
Arguments:
  branch (string, optional)
```

A merged or deleted session branch is recovered
automatically on the next write — this tool is the
explicit override on top of that.

---

### Resources

For clients that support MCP resources, the server
also exposes:

| Resource | URI | Use |
| -------- | --- | --- |
| Schema catalog | `infrahub://schema` | All kinds → labels; discover kinds before `get_nodes` / `node_upsert` |
| Schema kind detail | `infrahub://schema/{kind}` | One kind's attributes, relationships, and valid `get_nodes` filter keys |
| GraphQL schema | `infrahub://graphql-schema` | Full GraphQL SDL — reference for complex `query_graphql` / `mutate_graphql` |
| Branches | `infrahub://branches` | Branches present, including the active session branch |

If your client does not support resources,
`get_schema` returns the same schema data.

---

### Tool Invocation Patterns

#### Pattern 1 — Typed single-kind read (preferred)

```text
1. Call get_nodes with kind + filters
   (or search_nodes for a substring match)
2. Read display labels, or set
   include_attributes=true for full dicts
3. Evaluate each node against the policy
4. Report violations
```

#### Pattern 2 — GraphQL correlation across kinds

```text
1. Call query_graphql for node type A
   (policy source)
2. Call query_graphql for node type B
   (current state)
3. Build a lookup set from A
4. Check each item in B against the set
5. Report gaps
```

#### Pattern 3 — Schema discovery first

```text
1. Read infrahub://schema (or call get_schema)
   to find the right kind name
2. Read infrahub://schema/{kind}
   (or get_schema(kind="...")) for valid filters
3. Construct the get_nodes call or GraphQL
   query with the correct kind + filters
```

#### Pattern 4 — Remediation write (branch-isolated)

```text
1. (Optional) get_session_info to see the
   active branch
2. node_upsert / node_delete / mutate_graphql
   — lands on the session branch, never
     the default branch
3. propose_changes(title=..., description=...)
   to open a Proposed Change
4. A human reviews and merges; nothing reaches
   the default branch until then
```

---

### Response Structure

GraphQL responses from `query_graphql` follow the
Infrahub GraphQL convention:

```json
{
  "DcimDevice": {
    "edges": [
      {
        "node": {
          "id": "17f3a...",
          "display_label": "par01-spine-01",
          "name": {
            "value": "par01-spine-01"
          },
          "role": { "value": "spine" }
        }
      }
    ]
  }
}
```

Navigate: `response.<Kind>.edges[].node` to get
individual objects. Treating the response as a flat
list of nodes — skipping the `edges` indirection —
returns nothing and looks like missing data, when
the data is actually one envelope away.

`get_nodes` returns a simpler shape — display labels
by default, or full attribute dicts when
`include_attributes` is true — so you don't parse
the `edges`/`node` envelope for typed reads.

---

### Branch Model

All **reads** (`get_nodes`, `search_nodes`,
`query_graphql`, `get_schema`) run against the
default branch (`main` by convention) unless you
pass a `branch` argument. To audit a proposed-change
branch, pass its name:

```text
mcp__infrahub__get_nodes({
  "kind": "DcimDevice",
  "branch": "cr-2026-03-change"
})
```

All **writes** (`node_upsert`, `node_delete`,
`mutate_graphql`) are branch-isolated and take **no**
branch argument. The first write of a session
auto-creates a branch named
`mcp/session-YYYYMMDD-<hex>`, and every write lands
there — never on the default branch. Your changes
become visible on the source of truth only after you
call `propose_changes` and a human approves the
merge. This is the review loop the old
`infrahub_create` / `infrahub_update`-on-`main` path
could bypass; the reworked server enforces it, so
there is no way to write straight to the default
branch.

Use `get_session_info` to confirm which branch your
writes are on, and `reset_session_branch` to start a
fresh change set or take control of a specific
branch. The branch-first principle across all
Infrahub write paths (MCP, `infrahubctl`, the Python
SDK) is covered in the shared rule
[../../infrahub-common/rules/workflow-branch-for-crud.md](../../infrahub-common/rules/workflow-branch-for-crud.md).

Reference:
[Infrahub MCP Server Docs](https://docs.infrahub.app/mcp)
</content>
</invoke>
