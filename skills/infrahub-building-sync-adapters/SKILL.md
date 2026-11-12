---
name: infrahub-building-sync-adapters
description: >-
  Builds an infrahub-sync source adapter and validates it against the customer's live system through a sync config in the customer's repository.
  TRIGGER when: writing a new infrahub-sync adapter, adding a source system (REST API, SaaS tool, CMDB, directory) to infrahub-sync, probing a source API before an adapter spec, writing test fakes for an adapter's HTTP client, adding pagination, retries or rate-limit handling to an adapter, writing the sync config and identifiers for a new adapter, preparing an adapter pull request, modifying, debugging or extending an existing source adapter.
  DO NOT TRIGGER when: writing a destination adapter, source-side incremental reads, the infrahub-sync feature/v3-develop branch, changing infrahub-sync core, designing the destination schema (use infrahub-managing-schemas), a one-off CSV import (use infrahub-importing-data), converting NetBox device types (use infrahub-converting-netbox-device-types).
argument-hint: "[source-system]"
metadata:
  version: 1.3.0
  author: OpsMill
---

# infrahub-sync Source Adapter Builder

## Overview

Guides the work of adding a source system to
[infrahub-sync](https://github.com/opsmill/infrahub-sync):
the adapter, its tests, example, docs and pull request in
the infrahub-sync repository, and a sync configuration in
the customer's repository that validates the adapter
against the customer's live system.

The work spans two repositories on purpose. The bugs in
the adapters this skill comes from (Microsoft Graph for
Entra ID, and Webex) were found because the team could
query and sync against the customer's real system. Unit
tests built from documentation passed hundreds of times
while the live system behaved differently. So the
workflow starts by capturing the live API, builds the
tests from those captures, and ends with a live sync to
an Infrahub branch before the pull request.

The skill targets the infrahub-sync `main` branch
contract.

## Project Context

Adapters in this checkout, if this is infrahub-sync:
!`ls infrahub_sync/adapters/ 2>/dev/null | head -20`

Sync projects in this repository, if this is a customer
repository:
!`find . -maxdepth 3 -name "config.yml" -path "*sync*" 2>/dev/null | head -10`

If invoked with an argument (for example
`/infrahub:building-sync-adapters netinventory`), treat
it as the source system the adapter reads.

## When to Use

- A customer wants data from a system infrahub-sync has
  no adapter for, and the generic REST adapter's single
  read per resource is not enough.
- An existing source adapter needs pagination, retries,
  rate-limit handling, a new endpoint or a bug fix.
- An adapter exists and the customer's sync
  configuration, its `identifiers` or its first live run
  needs to be written or debugged.
- An adapter pull request is about to be opened.

## When NOT to Use

These are out of scope:

- **Destination adapters.** Only the Infrahub adapter
  writes on `main`.
- **Source-side incremental reads.** The adapter keeps
  the default `CursorTier.NONE` and reads the source in
  full on every run. Infrahub-side incremental reads
  (`infrahub-sync sync --no-full-extract`) still apply.
- **The `feature/v3-develop` contract.** Phase 0 stops
  when the checkout uses it.
- **Fixes to infrahub-sync core.** They become drafted
  issues, see
  [rules/scope-adapter-files-only.md](./rules/scope-adapter-files-only.md).
- **Designing the destination schema.** Hand it to
  `infrahub-managing-schemas`.

## Approval Points

Stop and wait for the user's explicit approval at these
four points, and at no others unless something fails:

| # | When | What the user approves |
| - | ---- | ---------------------- |
| 1 | End of phase 1 | `api-behavior.yml` |
| 2 | End of phase 2 | The spec |
| 3 | Phase 5, before the first `infrahub-sync sync` | Writing to the Infrahub branch, after the user has seen the `diff` |
| 4 | Phase 6, before push and pull request | The pull request description and the commits |

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Probe | `probe-` | Capture the live API and record its behavior before the spec |
| CRITICAL | Test | `test-` | Test fakes built from the captures, enforcing the behavior file |
| HIGH | Retry | `retry-` | Default retry and rate-limit policy |
| CRITICAL | Mapping | `mapping-` | Sync identifiers against the destination human-friendly ID, data check |
| HIGH | Scope | `scope-` | Adapter files only; core problems become drafted issues |
| HIGH | Gate | `gate-` | Full check list in the pull request |

## Workflow

Follow the phases in order. Each phase's output is the
input of the next one.

### Phase 0: Preflight

Check, and stop with a message at the first failure:

1. **The infrahub-sync checkout follows the `main`
   contract.** If `BUILTIN_ADAPTER_CAPABILITIES` exists
   under `infrahub_sync/`, the checkout is on
   `feature/v3-develop`: stop and tell the user this
   skill covers `main` only.
2. **Infrahub is reachable** (`infrahubctl info`) and its
   token is in the `INFRAHUB_API_TOKEN` environment
   variable.
3. **API login works with the integration account**, the
   account the sync will run as. Some systems refuse
   Basic authentication for interactive or admin
   accounts.
4. **The adapter name** is one lowercase word with no `-`
   and no `_`, with a `sync` suffix when it equals the
   vendor SDK's import name.

The commands and the reasons behind the naming rule are
in [reference.md](./reference.md#phase-0-preflight-details).

### Phase 1: Probe the live API

Query every endpoint the sync needs with the integration
account, save the responses with their headers under
`captures/`, and write `api-behavior.yml` from them. Read
[rules/probe-capture-before-spec.md](./rules/probe-capture-before-spec.md)
before the first request, and use the file format in
[reference.md](./reference.md#api-behavior-file-api-behavioryml).

**Approval point 1:** show the user `api-behavior.yml`.

### Phase 2: Spec

Write the spec in the infrahub-sync checkout. It cites
the `api-behavior.yml` entry of every endpoint, follows
the captures where they disagree with the vendor
documentation, and numbers every requirement in one
table that the final audit in phase 6 uses. Details in
[reference.md](./reference.md#phase-2-spec-details).

**Approval point 2:** show the user the spec.

### Phase 3: Adapter code and tests

1. Create the branch from `origin/main`.
2. Write `<Name>Adapter` and `<Name>Model` in
   `infrahub_sync/adapters/<name>.py`, following the
   contract in
   [reference.md](./reference.md#adapter-contract-on-main).
3. Give the HTTP client the default retry policy from
   [rules/retry-default-policy.md](./rules/retry-default-policy.md),
   with the overrides `api-behavior.yml` records.
4. Copy the redacted captures to `tests/fixtures/<name>/`
   and build the test fakes from them, as
   [rules/test-fakes-from-captures.md](./rules/test-fakes-from-captures.md)
   describes, before writing the tests that use them.
5. Write the example under `examples/`, the docs page and
   the news fragment.
6. After each commit, run the scope check in
   [rules/scope-adapter-files-only.md](./rules/scope-adapter-files-only.md).
   A helper the adapter needs is a private function in
   the adapter module; a change core needs is a drafted
   issue.

### Phase 4: Target schema and customer sync config

Work in the customer's repository.

1. **Schema step.** This is guidance, not a rule:
   1. For each source resource, look for an existing node
      in the repository's `schemas/` and in the schema
      loaded on the running Infrahub.
   2. If a node exists, map to it. When it has no
      attribute for the source's stable ID (the Entra
      adapter needed `object_id`, the Webex one
      `webex_location_id`), add one. Make it optional,
      and unique only when the source always fills it,
      because an optional unique attribute fails as soon
      as two nodes leave it empty. Never map a computed
      attribute.
   3. If no node exists, hand off to
      `infrahub-managing-schemas`, and wait for the user's
      approval of the new schema.
2. **Sync config.** Write `sync/<project>/config.yml`.
   Read
   [rules/mapping-identifiers-match-hfid.md](./rules/mapping-identifiers-match-hfid.md)
   before setting `identifiers`, and run its data check
   before the first run.
3. **Core limits.** Warn the user about the known
   infrahub-sync core limits in
   [reference.md](./reference.md#known-infrahub-sync-core-limits)
   that apply to this sync.

### Phase 5: Live validation

1. Add `.infrahub-sync-cache/` to the customer
   repository's `.gitignore` before the first run: the
   cache holds snapshots of source data.
2. Create an Infrahub branch and load the schema on it.
3. Run `infrahub-sync generate`, then `infrahub-sync
   diff` against that branch, and show the user the diff.
4. **Approval point 3:** run `infrahub-sync sync` to the
   branch only after the user approves.
5. Run `infrahub-sync diff` again. It must report no
   changes; any change means the adapter or the mapping
   does not round-trip.

The commands are in
[reference.md](./reference.md#phase-5-live-validation-commands).

A bug the live run finds goes back to phase 3: capture
the response that shows it, make the fake serve it, write
the failing test, then fix the adapter. A bug in
infrahub-sync core becomes a drafted issue, not a fix.

### Phase 6: Checks and pull request

Run every check in
[rules/gate-full-check-list.md](./rules/gate-full-check-list.md),
including the news fragment, the docs pages and the spec
documents re-read against the code. Mark every numbered
requirement of the spec met, partly met or not met.

**Approval point 4:** show the user the pull request
description, with its checks section, and the commits.
Push and open the pull request only after the user
approves.

## Supporting References

- **[reference.md](./reference.md)**: the
  `api-behavior.yml` format, the capture format and
  redaction, preflight commands, the adapter contract on
  `main`, spec details, live validation commands, and
  the known core limits.
- **[rules/_sections.md](./rules/_sections.md)**: the
  rule categories.
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
