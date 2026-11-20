---
name: infrahub-managing-sync-configs
description: >-
  Writes, changes and debugs an infrahub-sync config.yml in the customer's repository for a source adapter that already exists, and validates it with a sync to an Infrahub branch.
  TRIGGER when: writing, changing or debugging an infrahub-sync config.yml or sync project, choosing the identifiers of a schema_mapping entry, mapping source fields to Infrahub attributes and relationships, adding an attribute for a source system's stable ID to the destination schema for a sync, running infrahub-sync generate, diff or sync, validating a sync against an Infrahub branch, a sync that merges records or stops on one bad record.
  DO NOT TRIGGER when: the source system has no infrahub-sync adapter, or the adapter has a bug or is missing a feature (use infrahub-building-sync-adapters), designing a new destination schema node (use infrahub-managing-schemas), a one-off CSV import (use infrahub-importing-data), the infrahub-sync feature/v3-develop branch.
argument-hint: "[sync-project]"
metadata:
  version: 1.4.0
  author: OpsMill
---

# infrahub-sync Config Manager

## Overview

Guides the work on an
[infrahub-sync](https://github.com/opsmill/infrahub-sync)
configuration in the customer's repository: the
`config.yml` that maps a source system onto the
customer's Infrahub schema, the schema attributes the
mapping needs, and the live run that proves the mapping
works.

The adapter already exists. Reading the source system is
the adapter's job; this skill decides which records go to
which Infrahub node, under which key, and checks the
result on an Infrahub branch before anything reaches
`main`. When the live run shows that the adapter itself
is wrong, the work goes to
`infrahub-building-sync-adapters`.

The skill targets the infrahub-sync `main` branch
contract.

## Project Context

Sync projects in this repository:
!`find . -maxdepth 3 -name "config.yml" -path "*sync*" 2>/dev/null | head -10`

If invoked with an argument (for example
`/infrahub:managing-sync-configs from-netbox`), treat it
as the sync project to work on.

## When to Use

- A customer wants to sync a source system that
  infrahub-sync already has an adapter for (NetBox,
  Nautobot, Microsoft Graph, Webex and the others on
  `main`).
- A sync config needs a new mapping, field, reference,
  filter or transform.
- A sync merges records, creates duplicates, or stops on
  one bad record.
- `identifiers` need to be chosen or checked against the
  destination schema.
- An adapter has just been built with
  `infrahub-building-sync-adapters` and needs its
  customer config and its first live run.

## When NOT to Use

- **No adapter for the source system, or a bug in the
  adapter** (wrong pagination, missing field, retries).
  Use `infrahub-building-sync-adapters`.
- **Designing a new destination node.** Hand it to
  `infrahub-managing-schemas`.
- **The `feature/v3-develop` contract.** Preflight stops
  when the installed infrahub-sync uses it.
- **Fixes to infrahub-sync core.** They become drafted
  issues through `infrahub-reporting-issues`.

## Approval Points

Stop and wait for the user's explicit approval at these
two points, and at no others unless something fails:

| # | When | What the user approves |
| - | ---- | ---------------------- |
| 1 | Phase 2, only when the sync needs a new or changed schema | The schema change |
| 2 | Phase 4, before the first `infrahub-sync sync` | Writing to the Infrahub branch, after the user has seen the `diff` |

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Mapping | `mapping-` | Sync identifiers against the destination human-friendly ID, data check |

## Workflow

Follow the phases in order.

### Phase 1: Preflight

Check, and stop with a message at the first failure:

1. **The installed infrahub-sync follows the `main`
   contract.** If it defines
   `BUILTIN_ADAPTER_CAPABILITIES`, it is on
   `feature/v3-develop`: stop and tell the user this
   skill covers `main` only.
2. **The source system has an adapter.** If it has none,
   or the user reports an adapter bug, hand off to
   `infrahub-building-sync-adapters`.
3. **Infrahub is reachable** (`infrahubctl info`) and its
   token is in the `INFRAHUB_API_TOKEN` environment
   variable.

The commands are in
[reference.md](./reference.md#preflight-commands).

### Phase 2: Destination schema

This is guidance, not a rule:

1. For each source resource, look for an existing node in
   the repository's `schemas/` and in the schema loaded
   on the running Infrahub.
2. If a node exists, map to it. When it has no attribute
   for the source's stable ID (the Entra ID sync needed
   `object_id`, the Webex one `webex_location_id`), add
   one. Make it optional, and unique only when the source
   always fills it, because an optional unique attribute
   fails as soon as two nodes leave it empty. Never map a
   computed attribute. **Approval point 1:** wait for the
   user's approval of the schema change before loading
   it.
3. If no node exists, hand off to
   `infrahub-managing-schemas`. **Approval point 1:**
   wait for the user's approval of the new schema.

### Phase 3: Sync config

1. Write or change `sync/<project>/config.yml`, using the
   keys in [reference.md](./reference.md#config-keys-on-main).
2. Read
   [rules/mapping-identifiers-match-hfid.md](./rules/mapping-identifiers-match-hfid.md)
   before setting `identifiers`, and run its data check
   before the first run.
3. Warn the user about the known infrahub-sync core
   limits in
   [reference.md](./reference.md#known-infrahub-sync-core-limits)
   that apply to this sync.

### Phase 4: Live validation

1. Add `.infrahub-sync-cache/` to the customer
   repository's `.gitignore` before the first run: the
   cache holds snapshots of source data.
2. Create an Infrahub branch and load the schema on it.
3. Run `infrahub-sync generate`, then `infrahub-sync
   diff` against that branch, and show the user the diff.
4. **Approval point 2:** run `infrahub-sync sync` to the
   branch only after the user approves.
5. Run `infrahub-sync diff` again. `diff` reads the
   live source again, so a record created or changed in
   the source since the sync shows as a create or
   update; check those against the source first. Any
   other create or update means the adapter or the
   mapping does not round-trip. Deletions of existing
   nodes the source does not hold are expected, because
   the Infrahub adapter does not delete.

The commands are in
[reference.md](./reference.md#live-validation-commands).

A problem the live run finds goes to one of three places:

- **The mapping** (wrong key, field, reference or
  filter): fix `config.yml` in phase 3 and run phase 4
  again.
- **The adapter** (a record the source holds is missing
  or wrong in what the adapter reads): hand off to
  `infrahub-building-sync-adapters` with the source
  response that shows it.
- **infrahub-sync core**: draft an issue with
  `infrahub-reporting-issues`, not a fix.

## Supporting References

- **[reference.md](./reference.md)**: preflight
  commands, the config keys on `main`, live validation
  commands, and the known core limits.
- **[rules/_sections.md](./rules/_sections.md)**: the
  rule categories.
- **[../infrahub-building-sync-adapters/SKILL.md](../infrahub-building-sync-adapters/SKILL.md)**:
  a source with no adapter, or an adapter bug.
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**:
  new destination nodes, and changes to a node's
  `human_friendly_id`.
- **[../infrahub-analyzing-data/SKILL.md](../infrahub-analyzing-data/SKILL.md)**:
  checking the nodes already in Infrahub, such as the
  parents a sync references.
- **[../infrahub-common/rules/connectivity-server-check.md](../infrahub-common/rules/connectivity-server-check.md)**:
  checking the Infrahub server before any command that
  needs it.
- **[../infrahub-common/rules/workflow-branch-for-crud.md](../infrahub-common/rules/workflow-branch-for-crud.md)**:
  why every write goes to a branch first.
