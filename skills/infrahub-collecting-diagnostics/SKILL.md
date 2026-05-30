---
name: infrahub-collecting-diagnostics
description: >-
  Collects everything an Infrahub expert needs to debug a problem remotely and
  packages it as a sanitized local bundle. Detects deployment topology
  (Docker Compose / Kubernetes / local dev), runs read-only diagnostics, runs
  deterministic flag checks for common root causes, auto-redacts secrets, and
  stops at a user-review gate.
  TRIGGER when: Infrahub is broken/failing/erroring, the user asks for help
  debugging, wants to collect logs/diagnostics, prepares a hand-off for OpsMill
  support, or reports a crash/timeout/connection issue.
  DO NOT TRIGGER when: filing a public GitHub issue (use infrahub-reporting-issues),
  or running normal operational queries (use infrahub-analyzing-data).
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - WebFetch
  - Write
metadata:
  version: 1.2.5
  author: OpsMill
---

# Infrahub Diagnostics Collector

## Overview

When an Infrahub user reports a problem, an expert
(OpsMill support, or a senior engineer) needs a
consistent set of artifacts to triage it: logs,
config, version info, branch state, environment
fingerprints. This skill walks the user through
producing that artifact set as a single
`infrahub-diagnostics-YYYYMMDD-HHMMSS/` directory in
their working directory.

The skill is a **collector**. It runs read-only
commands, auto-redacts known secrets, pauses for the
user to review the redaction summary, then finalizes
the bundle. It does not file a GitHub issue (use
`infrahub-reporting-issues` for that), does not
diagnose root cause beyond a small set of
deterministic flag checks, and does not mutate
Infrahub state.

The bundle is built so that an expert, opening it for
the first time, can answer "what version, what
deployment, what changed recently, what failed" by
reading `README.md` and `manifest.yml` alone.

## When to Use

Trigger this skill when the user says things like:

- "Infrahub is broken / failing / erroring"
- "Help me debug this"
- "I need to collect logs to send to OpsMill"
- "Something went wrong after the upgrade"
- "My proposed change is stuck"
- "The UI is throwing 500s"

Do not trigger when:

- The user wants to file a public GitHub issue
  (use `infrahub-reporting-issues`)
- The user is asking operational questions about
  data ("how many devices in site X")
  (use `infrahub-analyzing-data`)
- The user wants to audit their schema against
  best practices (use `infrahub-auditing-repo`)

## Workflow

Follow these steps in order. Three user-gates;
everything else is automatic.

### 1. Capture the problem

Ask the user to describe the problem in their own
words if they haven't already. Don't probe yet —
listen for product names, version numbers, error
messages, workflow context.

### 2. Establish baseline

Detect deployment topology by trying, in order:

1. `docker compose ps` (Compose)
2. `kubectl -n infrahub get pods` (Kubernetes)
3. `tasks/demo.py` plus `invoke demo.status`
   (local dev)
4. Manual fallback — ask the user

Then collect baseline artifacts (see
[bundle-layout](rules/bundle-layout.md) for the
exact files). The baseline log window is 24 hours
unless the user changes it. Telemetry
(`infrahubctl telemetry export`) is included unless
`INFRAHUB_TELEMETRY_OPTOUT=true` is set on the
server.

### 3. Classify into a category (user-gate)

Ask the bug-report-template fields verbatim
(see [manifest-template](rules/manifest-template.md))
and use the answers to assign one of the categories
in this skill's catalog. Confirm the classification
with the user. The user can override; they can also
choose **everything** mode, which runs every
category's depth collection.

The categories are:

| # | Category | When |
| - | -------- | ---- |
| 1 | `installation-startup` | Containers crash on `docker compose up`; healthchecks loop; port conflicts |
| 2 | `upgrade` | After `infrahub upgrade` or `helm upgrade`; branches stuck in `NEED_UPGRADE_REBASE` |
| 3 | `git-sync` | Repo state `Error`/`Unknown`; `CommitNotFoundError`; schemas not loaded from repo |
| 4 | `task-worker-pipeline` | Tasks stuck `RUNNING`/`MERGING`; worker CrashLoopBackOff |
| 5 | `schema-load` | `schema check` rejects file; `/api/schema/load` hangs; schema hash drift |
| 6 | `check-generator-transform` | Pipeline check red; `infrahubctl <kind>` raises; Jinja2 transform fails |
| 7 | `graphql-api` | HTTP 5xx; non-nullable field errors; timeouts |
| 8 | `performance` | Slow UI, slow diff, OOM kills, browser hangs |
| 9 | `auth-permissions` | OAuth/OIDC login fails; default role can't create PC; JWT mismatch |
| 10 | `branch-merge` | Branch stuck `MERGING`/`DELETING`; failed merge leaves partial state |

### 4. Targeted collection

Run the category-specific commands documented in
`reference.md`. Always pull logs from every
`task-worker` replica (see
[multi-replica-coverage](rules/multi-replica-coverage.md));
recent race-condition bugs hide root cause when
only one replica is sampled.

### 5. Run flag checks

Run the deterministic flag-check catalog (see
`flag-checks.md`) against the collected files.
Write hits to `bundle/flags.yml`. Flag checks are
hints, not diagnoses (see
[flag-checks-deterministic](rules/flag-checks-deterministic.md)).

### 6. Redact and present a review summary (user-gate)

Apply Tier 1 auto-redaction (see
[redaction-tiers](rules/redaction-tiers.md)). Then
print a one-screen summary: counts of replacements,
samples of distinct IPs/hostnames/customer
strings/webhook URLs. For each sample group, ask
the user `keep` / `redact-all` / `case-by-case`.
Apply the choices. Log every replacement to
`bundle/redaction-report.txt`.

### 7. Finalize the bundle

Write `manifest.yml` and `README.md`. Print the
tarball command (`tar czf infrahub-diagnostics-*.tgz
infrahub-diagnostics-*/`). The bundle is now ready
to hand to an expert.

### 8. Hand-off (user-gate)

Print the expert-ready short summary (3-5 lines).
If the user then says they also want to file a
public GitHub issue, hand off to
`infrahub-reporting-issues` — see
[cross-link-reporting-issues](rules/cross-link-reporting-issues.md).
Never duplicate that skill's routing logic here.

## Rule Categories

| Prefix | Category | Description |
| ------ | -------- | ----------- |
| workflow | Workflow | User-gate semantics, step ordering |
| collection | Collection | Read-only command policy |
| multi-replica | Coverage | Multi-worker log collection |
| redaction | Redaction | Two-tier secret/PII masking |
| deployment | Detection | Topology detection order |
| bundle | Bundle | On-disk bundle structure |
| manifest | Manifest | manifest.yml field contract |
| flag-checks | Flag checks | Deterministic-only hint emission |
| cross-link | Cross-linking | Hand-off to reporting-issues |

See [rules/_sections.md](rules/_sections.md) for the
index.

## Supporting References

- [reference.md](reference.md) — exact commands per
  deployment topology (Compose, Kubernetes, local
  dev), environment-variable catalog, service-name
  map. **Read in step 4.**
- [examples.md](examples.md) — three end-to-end
  walk-throughs: git-sync failure, upgrade with
  stuck branch, performance investigation.
- [flag-checks.md](flag-checks.md) — full catalog
  of deterministic checks with patterns, severity,
  and related issue links. **Read in step 5.**
- [../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)
  — for git-sync and check/generator/transform
  categories.

## Anti-patterns

- **Running anything that mutates state.** No
  `infrahubctl schema load`, no `docker compose
  down`, no `kubectl delete`. Read-only only.
- **Sampling one replica when there are many.**
  Multi-worker race conditions are common in recent
  releases; missing one replica's logs hides the
  bug.
- **Skipping the redaction review gate.** The Tier
  2 review is non-negotiable. The bundle must be
  safe to share when finalized.
- **Claiming root cause.** This skill produces
  hints (flag checks), not diagnoses. The expert
  does the actual debugging.
- **Filing a GitHub issue from this skill.** That's
  `infrahub-reporting-issues`. Cross-link, don't
  duplicate.
