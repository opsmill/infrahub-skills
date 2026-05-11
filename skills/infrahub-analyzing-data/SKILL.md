---
name: infrahub-analyzing-data
description: >-
  Analyzes and correlates live Infrahub data via the MCP server — answers operational questions, detects drift, and investigates impact.
  TRIGGER when: querying infrastructure data, checking compliance, investigating change impact, producing ad-hoc reports.
  DO NOT TRIGGER when: writing automated checks, building transforms, designing schemas, populating data files.
  ALWAYS pass the user's question verbatim as args — this skill runs in a forked context and cannot see the parent conversation. Invoking without args will fail.
context: fork
allowed-tools:
  - Read
  - Bash
argument-hint: "[question about infrastructure data]"
metadata:
  version: 1.2.4
  author: OpsMill
---

## Overview

Expert guidance for interactive data analysis
against a live Infrahub instance. This skill uses
the **Infrahub MCP server** to query, correlate,
and reason over infrastructure data on demand —
answering operational questions that span multiple
node types and relationships.

Use this skill for any question of the form
*"what does Infrahub currently know about X,
and how does it relate to Y?"*

Typical question patterns:

- **Compliance** — "Are all devices following
  the naming convention?"
- **Service impact** — "Which services are hosted
  on devices in this rack?"
- **Maintenance windows** — "Which devices are
  currently in a maintenance window, and what
  depends on them?"
- **Drift detection** — "Which realized devices
  differ from their topology design?"
- **Capacity** — "Which racks are over 80% full?"
- **Change impact** — "What BGP sessions, services,
  and IPs depend on this prefix?"
- **Inventory gaps** — "Which devices have no
  platform or OS version recorded?"

For **automated, pipeline-enforced** checks that
block proposed changes, see
`../infrahub-managing-checks/SKILL.md`.
For **repeatable scheduled reports** exported as
artifacts, see `../infrahub-managing-transforms/SKILL.md`.

## Project Context

This skill runs in a forked subagent context and has no visibility into the
parent conversation. The user's question MUST be passed via arguments.

- If invoked with arguments (e.g., `/infrahub:analyzing-data Which devices have no platform assigned?`),
  treat the arguments as the question to answer.
- If invoked with **no arguments**, do **not** guess, do **not** use any example
  question from this file, and do **not** proceed. Return immediately with:

  > **Error:** No question was passed to `infrahub-analyzing-data`. This skill
  > runs in a forked context and requires the user's question as args. Re-invoke
  > with the question, e.g.
  > `Skill(skill="infrahub-analyzing-data", args="<the user's question>")`.

## When to Use

- Answering operational questions interactively
  via natural language
- Cross-referencing two or more node types to find
  relationships or gaps
- Investigating the blast radius of a change before
  executing it
- Auditing data quality across the inventory
- Producing one-time or on-demand reports for
  stakeholders
- Exploring schema structure and data before writing
  a generator or check

## How It Works

The Infrahub MCP server exposes tools that let
Claude query Infrahub data directly.
The typical workflow:

1. **Query** — use MCP tools to fetch current state
   from Infrahub
2. **Correlate** — join, diff, or filter the data
   against a policy or second dataset
3. **Reason** — identify gaps, anomalies, or
   relationships
4. **Report** — surface findings with context and
   remediation hints

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | MCP Tools | `mcp-` | Available Infrahub MCP tools, invocation patterns, response structure |
| CRITICAL | Query Patterns | `query-` | GraphQL structures for fetching, filtering, and traversing relationships |
| HIGH | Correlation | `correlation-` | Joining, diffing, and reasoning over data from multiple queries |
| HIGH | Reporting Output | `reporting-` | Presenting findings: summaries, tables, per-object detail, remediation hints |
| MEDIUM | Approach Selection | `approach-` | When to use MCP analysis vs InfrahubCheck vs Transform |

## MCP Server Basics

When the Infrahub MCP server is connected, Claude
can call tools such as:

- **`mcp__infrahub__infrahub_query`** — Execute a
  GraphQL query (primary tool)
- **`mcp__infrahub__infrahub_list_schema`** — List
  available node kinds
- **`mcp__infrahub__infrahub_get`** — Retrieve a
  specific object by ID or filters
- **`mcp__infrahub__infrahub_create`** — Create an
  object (remediation, on a branch)
- **`mcp__infrahub__infrahub_update`** — Update an
  object (remediation, on a branch)

```graphql
# Example: find all devices in an active
# maintenance window
query MaintenanceDevices {
  MaintenanceWindow(status__value: "active") {
    edges {
      node {
        name { value }
        start_time { value }
        end_time { value }
        devices {
          edges {
            node {
              name { value }
              role { value }
              site {
                node { name { value } }
              }
            }
          }
        }
      }
    }
  }
}
```

## Typical Analysis Workflow

```text
1. Understand the question
   → "Which services depend on devices currently
      in a maintenance window?"

2. Identify the node types involved
   → MaintenanceWindow, DcimDevice, Service
     (or equivalent in your schema)

3. Query current state
   → mcp__infrahub__infrahub_query — one query
     per node type, or combined

4. Correlate the data
   → Join across node types, filter, count, diff

5. Report findings
   → Summarize with counts, list affected objects,
     suggest next steps
```

## Supporting References

- **[examples.md](./examples.md)** — Analysis
  patterns (naming, VLAN, BGP, maintenance,
  service impact)
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  — GraphQL query writing reference
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  — .infrahub.yml project configuration
- **[../infrahub-managing-checks/SKILL.md](../infrahub-managing-checks/SKILL.md)**
  — Automated pipeline checks (for enforcement)
- **[../infrahub-managing-transforms/SKILL.md](../infrahub-managing-transforms/SKILL.md)**
  — Transforms for scheduled report artifacts
- **[rules/](./rules/)** — Individual rules organized
  by category prefix
