# Infrahub MCP Server Tools Reference

The Infrahub MCP server allows Claude to interact with
a live Infrahub instance directly. When connected, it
exposes tools for querying data, discovering schemas,
and creating or updating objects.

**Prerequisite:** The Infrahub MCP server must be
connected to your AI assistant. If `mcp__infrahub__*`
tools are not available, the MCP server is not
configured — proceed without live queries and note
this limitation to the user.

---

## Available Tools

### `mcp__infrahub__infrahub_query`

Execute a raw GraphQL query against Infrahub. This is
the primary tool for fetching data.

```text
Arguments:
  query     (string, required)
    — GraphQL query string
  branch    (string, optional)
    — Branch name (default: main)
  variables (object, optional)
    — GraphQL variables for parameterized queries
```

**Example:**

```text
mcp__infrahub__infrahub_query({
  "query": "query { InfraDevice {
    edges { node { id name { value } } }
  } }"
})
```

**With variables:**

```text
mcp__infrahub__infrahub_query({
  "query": "query DevicesBySite(
    $site: String!
  ) { InfraDevice(
    site__name__value: $site
  ) { edges { node {
    id name { value }
  } } } }",
  "variables": { "site": "PAR01" }
})
```

---

### `mcp__infrahub__infrahub_list_schema`

List all available schema node kinds in the Infrahub
instance. Use this when you need to discover or
confirm exact kind names.

```text
Arguments: none
```

Returns a list of kind names (e.g., `InfraDevice`,
`IpamPrefix`, `NetworkBgpSession`).

---

### `mcp__infrahub__infrahub_get`

Retrieve a single object by ID or filters. Useful for
fetching full details of a specific object.

```text
Arguments:
  kind    (string, required)
    — Node kind (e.g., "InfraDevice")
  id      (string, optional)
    — Infrahub object ID
  filters (object, optional)
    — Attribute filters
```

---

### `mcp__infrahub__infrahub_create`

Create a new object in Infrahub.

```text
Arguments:
  kind   (string, required)
    — Node kind
  data   (object, required)
    — Attribute values
  branch (string, optional)
    — Branch (default: main)
```

Always create on a **named branch** (not main) so
changes can be reviewed in a proposed change.

---

### `mcp__infrahub__infrahub_update`

Update an existing object in Infrahub.

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

Always update on a **named branch** — never write
directly to `main`.

---

## Response Structure

All query responses follow the Infrahub GraphQL
convention:

```json
{
  "InfraDevice": {
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

Always navigate: `response.<Kind>.edges[].node`
to get individual objects.

---

## Branch Considerations

By default all MCP queries run against the `main`
branch. To query a different branch:

```text
mcp__infrahub__infrahub_query({
  "query": "...",
  "branch": "my-feature-branch"
})
```

- **Read operations:** Specify branch if inspecting a
  proposed change or feature branch
- **Write operations** (create/update): Always use a
  named branch so changes can be reviewed before merge

---

## Common Patterns

### Schema Discovery First

When you don't know the exact kind name:

```text
1. Call mcp__infrahub__infrahub_list_schema
   to find the right kind name
2. Construct your GraphQL query using
   the correct kind
3. Proceed with your workflow
```

### Data Sampling

Before creating files or writing code, sample live
data to understand the actual shape:

```text
1. Query a small set of objects to see the
   response structure
2. Use the response to inform your file
   creation or code design
```

---

Reference:
[Infrahub MCP Server Docs](https://docs.infrahub.app/integrations/mcp)
