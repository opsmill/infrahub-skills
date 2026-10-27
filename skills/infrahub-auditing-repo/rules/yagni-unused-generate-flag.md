---
title: yagni-unused-generate-flag
impact: MEDIUM
ladder_step: 3
tags: audit, yagni, profile, object-template, dead-feature
---

# Rule: yagni-unused-generate-flag

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 3 — capability enabled with no consumer

## What It Checks

`generate_profile: true` or `generate_template: true` set on a
node for which the repo contains **no consumer**: no Profile
instances / `profiles:` assignments for a profile flag, and no
template instances / `object_template` references for a template
flag. The flag advertises a feature nobody uses.

## Why it matters

An enabled `generate_*` flag is a promise: it generates a
companion `Profile<Kind>` / `Template<Kind>` kind and invites
users toward a workflow. When nothing in the repo creates or
assigns those instances, the capability is speculative — the
classic YAGNI smell of building for a use that hasn't arrived.
It clutters the schema surface and misleads readers into
thinking a Profile/template workflow exists.

This is advisory (MEDIUM): the schema still loads and nothing
breaks. Flag it so the author either wires up the workflow or
drops the flag until it is needed.

## Checks

1. A node has `generate_profile: true` and/or
   `generate_template: true`.
2. For `generate_profile: true`, search `objects/` (and any
   other data directories) for a Profile instance of the
   generated kind or a `profiles:` assignment referencing it.
   None found means the flag is unused.
3. For `generate_template: true`, search for a template
   instance of the generated kind or an `object_template`
   reference. None found means the flag is unused.
4. Flag each unused flag independently — a node can have one
   flag in use and the other unused.

## What NOT to flag

- Flags with **any** consumer in the repo (a Profile instance,
  a `profiles:` assignment, a template, or an `object_template`
  reference) — the feature is in use.
- Nodes in a schema-only / library package whose data lives in a
  separate repo (state this assumption in the finding if the
  repo is clearly a shared schema library).

## Common Issues

- `generate_profile: true` added while designing the schema
  "in case we need per-fleet defaults later," with no Profile
  ever created — drop the flag until a Profile is actually
  needed.
- `generate_template: true` left enabled after a prototype
  Object Template was deleted during cleanup, with the flag
  never removed alongside it.

## Finding shape

Emit one finding per unused flag:
`{ "rule": "yagni-unused-generate-flag", "severity": "MEDIUM", "ladder_step": 3, "file": "<schema file>", "line": "<n>" }`
