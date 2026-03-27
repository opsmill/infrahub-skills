---
title: MCP Tools for Compliance Analysis
impact: CRITICAL
tags: mcp, tools, query, compliance
---

## MCP Tools for Compliance Analysis

Impact: CRITICAL

For full tool definitions, arguments, response
structure, and branch handling, see the shared
reference:
**[../../common/mcp-tools-reference.md](../../common/mcp-tools-reference.md)**

This rule covers analyst-specific invocation patterns
for compliance and remediation workflows.

---

### Compliance Invocation Patterns

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

See the "Schema Discovery First" pattern in the
[shared MCP reference](../../common/mcp-tools-reference.md#common-patterns),
then proceed with your compliance query.

---

### Remediation via MCP

When analysis reveals violations that can be fixed
directly, use MCP tools for remediation:

- **Create missing objects** — Use
  `mcp__infrahub__infrahub_create` to add objects that
  should exist (e.g., missing loopback interfaces,
  required tags)
- **Fix incorrect values** — Use
  `mcp__infrahub__infrahub_update` to correct
  attributes that violate policy (e.g., wrong VLAN
  assignment, non-compliant names)

Always remediate on a **named branch** so changes go
through a proposed change review. Never write directly
to `main`.

```text
mcp__infrahub__infrahub_create({
  "kind": "InfraInterfaceL3",
  "data": {
    "name": { "value": "Loopback0" },
    "device": "17f3a..."
  },
  "branch": "fix-missing-loopbacks"
})
```

---

### Auditing Proposed Change Branches

To compare current state against a proposed change,
query both branches and diff the results:

```text
1. Query main branch (default)
2. Query proposed change branch:
   mcp__infrahub__infrahub_query({
     "query": "...",
     "branch": "cr-2026-03-change"
   })
3. Compare results to identify what changed
```

Reference:
[Infrahub MCP Server Docs](https://docs.infrahub.app/integrations/mcp)
