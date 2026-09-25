---
name: infrahub-planning-upgrades
description: >-
  Plans a version-by-version Infrahub upgrade path and scores each release's breaking
  changes against the user's repository and instance.
  TRIGGER when: planning an Infrahub upgrade, asking what breaks between two versions,
  checking upgrade impact before a maintenance window, updating an existing upgrade plan
  after the target release or the repository moved, debugging a plan that missed a
  breaking change.
  DO NOT TRIGGER when: auditing a repo against best practices, querying live data,
  designing schemas.
context: fork
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Write
argument-hint: "<current version> to <target version>"
# STAGE-2 SCAFFOLD: false only because this is not yet a usable skill. Stage 3
# must flip this to true AND add docs/docs/skills-reference/planning-upgrades.mdx
# — `uv run invoke lint` fails on a user-invocable skill with no reference page,
# so the gate enforces the pair.
user-invocable: false
metadata:
  version: 0.0.0
  author: OpsMill
---

# Infrahub Upgrade Path Planner

<!--
STAGE-2 SCAFFOLD ONLY.

This file carries the output contract and nothing else, so the eval tasks have an
artifact to produce and the graders have a structure to parse. Every rule the four
eval tasks score - sequential N-1 hops, enumerating intermediate releases, backing
each verdict with evidence, and the read-only boundary - is deliberately ABSENT.

`implementing-skill-changes` writes the real body, the four rules under rules/, the
Rule Categories table, and `rules/_sections.md`. Do not treat this as the skill.
-->

## Overview

Produces an upgrade plan for moving an Infrahub deployment from one release to
another.

## Output contract

Write the plan to `UPGRADE_PLAN.md`.

- One `##` section per version hop.
- Each hop section carries a findings table with exactly these columns:

  | Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |
  | ------ | ------- | ---- | -------- | ---- | -------- | -------- | ------ | ------ |

- `Kind` is `breaking` or `preparation`.
- `Severity` is `critical`, `warning`, or `info`.
- `When` is `before`, `during`, or `after`.
- `Affected` is `yes`, `no`, or `unknown`.
