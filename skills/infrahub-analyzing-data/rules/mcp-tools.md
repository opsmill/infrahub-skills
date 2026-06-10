---
title: Infrahub MCP Server Tool Reference
impact: CRITICAL
tags: mcp, tools, query, infrahub
---

## Infrahub MCP Server Tool Reference

Impact: CRITICAL

The Infrahub MCP server exposes a set of tools that
allow Claude to interact with a live Infrahub
instance directly. Compliance workflows depend on
calling these tools correctly to fetch, evaluate,
and optionally update data.

### Why it matters

MCP tools run against a live instance, so a
malformed GraphQL query comes back as "query
failed" with a partial reason — the difference
between an answer and a stack trace is the exact
shape of the kind name, the `edges`/`node` envelope,
and the attribute filter syntax. Schema introspection
via `mcp__infrahub__infrahub_list_schema` is the
cheap first step; reaching for `infrahub_query`
without it leads to round trips that fail on a typo
the introspection call would have surfaced. The same
care applies to writes — `infrahub_create` and
`infrahub_update` issued against `main` skip the
proposed-change review loop entirely, which is the
single guard against accidental data drift from a
remediation script.

---

### Available Tools

#### `mcp__infrahub__infrahub_query`

Execute a raw GraphQL query against Infrahub. This
is the primary tool for compliance data retrieval.

```text
Arguments:
  query  (string, required)
    — GraphQL query string
  branch (string, optional)
    — Branch name (default: main)
  variables (object, optional)
    — GraphQL variables for
      parameterized queries
```

**Correct usage:**

```text
mcp__infrahub__infrahub_query({
  "query": "query { DcimDevice {
    edges { node { id name { value } } }
  } }"
})
```

**With variables:**

```text
mcp__infrahub__infrahub_query({
  "query": "query DevicesBySite(
    $site: String!
  ) { DcimDevice(
    site__name__value: $site
  ) { edges { node {
    id name { value }
  } } } }",
  "variables": { "site": "PAR01" }
})
```

---

#### `mcp__infrahub__infrahub_list_schema`

List all available schema node kinds in the
Infrahub instance. Use this when you don't know
the exact kind name for a node type.

```text
Arguments: none
```

Returns a list of kind names (e.g., `DcimDevice`,
`IpamPrefix`, `NetworkBgpSession`).

---

#### `mcp__infrahub__infrahub_get`

Retrieve a single object by ID or
human_friendly_id. Useful for fetching the full
detail of a specific violation.

```text
Arguments:
  kind  (string, required)
    — Node kind (e.g., "DcimDevice")
  id    (string, optional)
    — Infrahub object ID
  filters (object, optional)
    — Attribute filters
```

---

#### `mcp__infrahub__infrahub_create`

Create a new object in Infrahub. Use for
remediation workflows (e.g., creating a missing
loopback interface).

```text
Arguments:
  kind   (string, required)
    — Node kind
  data   (object, required)
    — Attribute values
  branch (string, optional)
    — Branch (default: main)
```

Create on a **branch** (not main) so changes go
through a proposed change for review — writes to
`main` skip the review pipeline and land
unreviewed.

---

#### `mcp__infrahub__infrahub_update`

Update an existing object in Infrahub. Use for
remediation (e.g., correcting a wrong VLAN
assignment).

```text
Arguments:
  kind   (string, required)
    — Node kind
  id     (string, required)
    — Object ID
  data   (object, required)
    — Fields to update
  branch (string, optional)
    — Branch (default: main)
```

---

### Tool Invocation Patterns

#### Pattern 1 — Single query compliance

```text
1. Call mcp__infrahub__infrahub_query
   with your GraphQL
2. Parse response:
   data.<NodeKind>.edges[].node
3. Evaluate each node against the policy
4. Report violations
```

#### Pattern 2 — Multi-query correlation

```text
1. Call mcp__infrahub__infrahub_query
   for node type A (policy source)
2. Call mcp__infrahub__infrahub_query
   for node type B (current state)
3. Build lookup set from A
4. Check each item in B against the set
5. Report gaps
```

#### Pattern 3 — Schema discovery first

```text
1. Call mcp__infrahub__infrahub_list_schema
   to find the right kind name
2. Construct GraphQL query using the
   correct kind
3. Proceed with compliance query
```

---

### Response Structure

All query responses follow the Infrahub GraphQL
convention:

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

---

### Branch Considerations

By default all MCP queries run against the `main`
branch. To audit a proposed change branch:

```text
mcp__infrahub__infrahub_query({
  "query": "...",
  "branch": "cr-2026-03-change"
})
```

For remediation creates/updates, target a **named
branch**. Writes to `main` bypass the proposed
change review loop entirely, so a buggy remediation
script lands unreviewed on the source of truth.

Reference:
[Infrahub MCP Server Docs](https://docs.infrahub.app/integrations/mcp)
