---
name: infrahub-planning-upgrades
description: >-
  Plans a version-by-version Infrahub upgrade path and scores each release's breaking
  changes against the user's repository and instance, producing UPGRADE_PLAN.md.
  TRIGGER when: planning an Infrahub upgrade, asking what breaks between two versions,
  checking upgrade impact before a maintenance window, asked to "just run the upgrade",
  updating or extending an existing UPGRADE_PLAN.md after the target release or the
  repository moved, debugging a plan that missed a breaking change.
  DO NOT TRIGGER when: auditing a repo against best practices, querying live data,
  designing schemas, collecting diagnostics after a failed upgrade.
  ALWAYS pass the current and target versions as args: this skill runs in a forked
  context and cannot see the parent conversation.
context: fork
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Write
argument-hint: "<current version> to <target version>"
metadata:
  version: 1.3.0
  author: OpsMill
---

# Infrahub Upgrade Path Planner

## Overview

Produces `UPGRADE_PLAN.md`: the route from the running
Infrahub version to the target, one hop per minor
version, with every breaking change in that range
checked against this repository and, when reachable,
this instance.

**The plan describes how to upgrade; it does not
upgrade.** It never runs `infrahub upgrade`, a schema
load, or a branch write, and it never hands the user the
upgrade command. It may run and show read-only probes.
The user's deployment method (Docker Compose, Helm,
Enterprise, Community) decides the exact commands, and
the upgrade guide for that deployment owns them.

`Write` is granted for `UPGRADE_PLAN.md` only. `Bash` is
granted for reading release notes with `gh` and for the
read-only probes.

## Project Context

This skill runs in a forked context. The versions come
from the arguments, for example
`/infrahub:planning-upgrades 1.9.2 to 1.10.0`. With no
target, ask for one. With no current version, read it
from `infrahubctl info` (`Infrahub Version:`), and ask
if the server is unreachable.

## Workflow

1. **Fix the endpoints and the hops.** Infrahub
   supports upgrades only from the previous minor
   version (N-1), so 1.6.3 to 1.9.0 is three hops:
   1.6 to 1.7, 1.7 to 1.8, 1.8 to 1.9. Never plan a
   jump across minors, even when the user asks for
   "one go". Rolling up patches within the current
   minor first (1.10.8 to 1.10.10) is fine as its own
   section.
2. **Enumerate every release in the range, patches
   included, and read each one's notes.** Read
   [rules/sources-enumerate-every-hop.md](./rules/sources-enumerate-every-hop.md)
   before fetching anything: breaking changes ship in
   patch releases, and no machine-readable flag marks
   them.
3. **Inventory the repository.** Schema YAML,
   `.infrahub.yml`, GraphQL queries, and the Python
   checks, generators, and transforms. If an instance
   is reachable, confirm it with `infrahubctl info`
   ([connectivity-server-check](../infrahub-common/rules/connectivity-server-check.md))
   and read live data through the MCP read tools
   ([mcp-tools](../infrahub-analyzing-data/rules/mcp-tools.md)).
   The instance is optional; the repository is not.
4. **Give every finding a verdict and back it.** Read
   [rules/impact-verdict-needs-evidence.md](./rules/impact-verdict-needs-evidence.md)
   before filling the `Affected` and `Evidence`
   columns.
5. **Probe, read-only.** Read
   [rules/safety-read-only-probes.md](./rules/safety-read-only-probes.md)
   before running or showing any command, and again
   if the user asks you to run the upgrade.
6. **Write `UPGRADE_PLAN.md`** in the shape below.
   Each hop's steps are prose: take a backup, clear
   the `before` findings, upgrade to the hop's target
   following the upgrade guide, clear the `during` and
   `after` findings. Link the guide rather than
   transcribing it:
   <https://docs.infrahub.app/deploy-manage/maintain-upgrade/upgrade/overview>

## Plan Format

One `##` section per hop, in ascending order, with the
hop's two versions in the heading (`## 1.9 -> 1.10`).
Each hop carries one findings table with these nine
columns, in this order:

| Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |
| ------ | ------- | ---- | -------- | ---- | -------- | -------- | ------ | ------ |

| Column | Values |
| ------ | ------ |
| `Release` | one version, `X.Y.Z`, never a range |
| `Kind` | `breaking` or `preparation` |
| `Severity` | `critical`, `warning`, or `info` |
| `When` | `before`, `during`, or `after` the hop |
| `Affected` | `yes`, `no`, or `unknown` |

What each value means, and a worked example, are in
[reference.md](./reference.md). Read it before writing
the first row.

## Rule Categories

| Category | Prefix | Rules |
| -------- | ------ | ----- |
| Sources | `sources-` | [sources-enumerate-every-hop](./rules/sources-enumerate-every-hop.md) |
| Impact | `impact-` | [impact-verdict-needs-evidence](./rules/impact-verdict-needs-evidence.md) |
| Safety | `safety-` | [safety-read-only-probes](./rules/safety-read-only-probes.md) |

## Supporting References

- [reference.md](./reference.md): column semantics and
  an example plan. Read at step 6.
- [rules/_sections.md](./rules/_sections.md): the rule
  index.
