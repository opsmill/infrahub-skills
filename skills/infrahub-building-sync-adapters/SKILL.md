---
name: infrahub-building-sync-adapters
description: >-
  Builds an infrahub-sync source adapter from API responses captured on the live system; the customer's sync config and live run go to infrahub-managing-sync-configs.
  TRIGGER when: writing a new infrahub-sync adapter, adding a source system (REST API, SaaS tool, CMDB, directory) to infrahub-sync, probing a source API before an adapter spec, writing test fakes for an adapter's HTTP client, adding pagination, retries or rate-limit handling to an adapter, preparing an adapter pull request, modifying, debugging or extending an existing source adapter.
  DO NOT TRIGGER when: writing or debugging a customer's sync config.yml, or running generate, diff or sync on it (use infrahub-managing-sync-configs), destination adapters, source-side incremental reads, the infrahub-sync feature/v3-develop branch, changing infrahub-sync core, designing the destination schema (use infrahub-managing-schemas), a one-off CSV import (use infrahub-importing-data), converting NetBox device types (use infrahub-converting-netbox-device-types).
argument-hint: "[source-system]"
metadata:
  version: 1.4.0
  author: OpsMill
---

# infrahub-sync Source Adapter Builder

## Overview

Guides the work of adding a source system to
[infrahub-sync](https://github.com/opsmill/infrahub-sync):
the adapter, its tests, example, docs and pull request in
the infrahub-sync repository. The customer's sync
configuration and the live run that validates the
adapter against the customer's system belong to
`infrahub-managing-sync-configs`, which this skill hands
off to in phase 4.

The live run is part of the work on purpose. The bugs in
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

If invoked with an argument (for example
`/infrahub:building-sync-adapters netinventory`), treat
it as the source system the adapter reads.

## When to Use

- A customer wants data from a system infrahub-sync has
  no adapter for, and the generic REST adapter's single
  read per resource is not enough.
- An existing source adapter needs pagination, retries,
  rate-limit handling, a new endpoint or a bug fix.
- A live run with `infrahub-managing-sync-configs` shows
  an adapter bug.
- An adapter pull request is about to be opened.

## When NOT to Use

These are out of scope:

- **The customer's sync configuration** for an adapter
  that exists: its `config.yml`, `identifiers`, schema
  mapping and live runs. Use
  `infrahub-managing-sync-configs`.
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
three points, and at no others unless something fails.
The schema change and the first write to Infrahub are
approved in `infrahub-managing-sync-configs` during
phase 4. A retry limit longer than the 300 s default is
approved with `api-behavior.yml` or the spec; one needed
later counts as a failure, so stop and ask.

| # | When | What the user approves |
| - | ---- | ---------------------- |
| 1 | End of phase 1 | `api-behavior.yml` |
| 2 | End of phase 2 | The spec |
| 3 | Phase 6, before push and pull request | The pull request description and the commits |

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Probe | `probe-` | Capture the live API and record its behavior before the spec |
| CRITICAL | Test | `test-` | Test fakes built from the captures, enforcing the behavior file |
| HIGH | Retry | `retry-` | Default retry and rate-limit policy |
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
2. **API login works with the integration account**, the
   account the sync will run as. Some systems refuse
   Basic authentication for interactive or admin
   accounts.
3. **The adapter name** is one lowercase word with no `-`
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
   the news fragment. The docs page says that a record
   removed from the source stays in Infrahub, because
   `InfrahubModel` has no delete.
6. After each commit, run the scope check in
   [rules/scope-adapter-files-only.md](./rules/scope-adapter-files-only.md).
   A helper the adapter needs is a private function in
   the adapter module; a change core needs is a drafted
   issue.

### Phase 4: Customer config and live validation

Hand off to `infrahub-managing-sync-configs` in the
customer's repository. Give it the adapter name, the
path of the infrahub-sync checkout that holds the
adapter, and the source resources the spec covers. That
skill maps the resources onto the customer's schema,
writes the sync config, and runs the live validation on
an Infrahub branch, after its own preflight checks that
Infrahub is reachable. Do not write the sync config here.

### Phase 5: Fix what the live run finds

An adapter bug the live run finds comes back to phase 3:
capture the response that shows it, make the fake serve
it, write the failing test, then fix the adapter. Then
run the live validation in
`infrahub-managing-sync-configs` again. A mapping
problem stays with that skill. A bug in infrahub-sync
core becomes a drafted issue, not a fix.

### Phase 6: Checks and pull request

Run every check in
[rules/gate-full-check-list.md](./rules/gate-full-check-list.md),
including the news fragment, the docs pages and the spec
documents re-read against the code. Mark every numbered
requirement of the spec met, partly met or not met.

**Approval point 3:** show the user the pull request
description, with its checks section, and the commits.
Push and open the pull request only after the user
approves.

## Supporting References

- **[reference.md](./reference.md)**: the
  `api-behavior.yml` format, the capture format and
  redaction, preflight commands, the adapter contract on
  `main`, and spec details.
- **[rules/_sections.md](./rules/_sections.md)**: the
  rule categories.
- **[../infrahub-managing-sync-configs/SKILL.md](../infrahub-managing-sync-configs/SKILL.md)**:
  the customer's sync config, the destination schema
  mapping, the live validation commands, and the known
  infrahub-sync core limits.
- **[../infrahub-common/rules/connectivity-server-check.md](../infrahub-common/rules/connectivity-server-check.md)**:
  checking the Infrahub server before any command that
  needs it.
