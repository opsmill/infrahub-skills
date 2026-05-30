# Design — `infrahub-collecting-diagnostics`

**Status:** Approved (brainstorming gate)
**Date:** 2026-05-30
**Branch:** `ic-feat-skill-troubleshooting`

## Purpose

Collect everything an Infrahub expert needs to debug a
problem remotely, package it as a sanitized local
bundle, and stop at a user-review gate. The bundle is
the deliverable; the user hands it to OpsMill support
(Discord, enterprise Slack, email) out-of-band.

## Boundaries

This skill is deliberately **not**:

- `infrahub-reporting-issues` — files public GitHub
  issues and constrains the data to versions + OS
  only. This skill does the opposite: comprehensive
  collection for private hand-off.
- `infrahub-analyzing-data` — for normal operational
  queries. This skill triggers on breakage.
- `infrahub-auditing-repo` — offline schema
  compliance. This skill is runtime.
- A fixer — read-only collection plus deterministic
  flag hints. Never mutates Infrahub state.

At the end of the workflow, if the user wants to also
file a public issue, the skill cross-links to
`infrahub-reporting-issues` rather than duplicating
that flow.

## Identity

- **Skill name:** `infrahub-collecting-diagnostics`
- **Directory:** `skills/infrahub-collecting-diagnostics/`
- **Output:** `infrahub-diagnostics-YYYYMMDD-HHMMSS/`
  directory in the user's current working directory.

### Frontmatter description (draft)

```yaml
description: >-
  Collects everything an Infrahub expert needs to debug
  a problem remotely and packages it as a sanitized
  local bundle. Detects deployment topology
  (Docker Compose / Kubernetes / local dev), runs
  read-only diagnostics, runs deterministic flag checks
  for common root causes, auto-redacts secrets, and
  stops at a user-review gate.
  TRIGGER when: Infrahub is broken/failing/erroring,
  the user asks for help debugging, wants to collect
  logs/diagnostics, prepares a hand-off for OpsMill
  support, or reports a crash/timeout/connection issue.
  DO NOT TRIGGER when: filing a public GitHub issue
  (use infrahub-reporting-issues), or running normal
  operational queries (use infrahub-analyzing-data).
```

## Design Decisions

These are settled and shape every later decision:

| Decision | Choice | Why |
|---|---|---|
| Output destination | Local-only bundle directory | User hands to expert out-of-band; no opinion on how |
| Collection mode | Skill runs read-only commands directly | Faster than scripting; safe because all commands are read-only |
| Sensitive data | Auto-redact + user review gate | Bundle must be shareable by default, user spot-checks before finalize |
| Diagnosis depth | Collector + deterministic flag checks | No LLM-judged diagnosis; only pattern-match obvious causes |
| Collection structure | Symptom-first targeted (with "unsure" fallback) | Comprehensive on the right category, not blind everywhere |
| Baseline log window | 24 hours | Matches what support typically asks for |
| Telemetry export | Included by default, skip if opt-out | High-value, low-cost (~3-5 KB) |

## Workflow

A linear, gated workflow. Three user-gates; everything
else is automatic.

```
1. Capture problem          (user describes; skill listens, no probing yet)
2. Establish baseline       (detect deployment topology, version, edition; run probes)
3. Classify into category   (ask the bug-report-template fields)
4. Targeted collection      (per-category commands; multi-worker aware)
5. Run flag checks          (deterministic; emits flags.yml)
6. Redact + summary         (auto-redact secrets; sample IPs/hostnames; prompt)
   ── USER REVIEW GATE ──
7. Finalize bundle          (write manifest.yml, README.md; print tarball cmd)
8. Hand-off                 (print expert-ready summary; cross-link reporting-issues
                             if user then wants to file an issue)
```

### User-gate semantics

- **Step 3** — confirm classified category before any
  category-specific commands run. The user can override.
- **Step 6** — review redaction summary (counts +
  samples). User can mark groups as `keep`,
  `redact-all`, or `case-by-case`.
- **Step 8** — confirm before printing the
  expert-ready summary or invoking
  `infrahub-reporting-issues`.

### Universal-first questions

Step 1+3 mirror the [opsmill/infrahub bug-report
template](https://github.com/opsmill/infrahub/blob/main/.github/ISSUE_TEMPLATE/bug_report.yml)
verbatim, so `user-input/questions-answered.md` is
transcribable into a GitHub issue with no rework:

1. Infrahub version (cross-checked against
   `/api/config`)
2. Edition (Community / Enterprise — gates log
   forwarding and some diagnostics)
3. Deployment type (Docker Compose / Kubernetes-Helm
   / k3d / bare-metal / local dev via
   `invoke demo.start`)
4. Component (Frontend UI / API Server / Git
   Integration / Python SDK / infrahubctl CLI / Not
   Sure)
5. Current behavior
6. Expected behavior
7. Steps to reproduce
8. Error message verbatim
9. When did it start
10. Reproducibility (every time / intermittent / load-only)
11. What changed recently
12. Impact / urgency

### Deployment detection

Tried in order until one succeeds:

1. `docker compose ps` → Compose
2. `kubectl -n infrahub get pods` → Kubernetes
3. `tasks/demo.py` + `invoke demo.status` → local dev
4. Manual fallback: ask the user

Topology determines every later command shape. Service
names are stable across Compose and Helm
(`infrahub-server`, `task-worker`, `database`,
`cache`, `message-queue`, `task-manager`,
`task-manager-db`).

### Multi-replica coverage

Step 4 always pulls from every `task-worker` replica,
not just the first. Recent multi-worker race
conditions ([#9036](https://github.com/opsmill/infrahub/issues/9036),
[#9293](https://github.com/opsmill/infrahub/issues/9293),
[#9349](https://github.com/opsmill/infrahub/issues/9349))
hide root cause when only one replica's logs are
collected.

## Categories

Ten categories. UI bugs fold into the relevant
server-side category (typically `graphql-api` or
`performance`) with browser HAR/console added to
`user-input/`. Backup/restore folds into `upgrade` for
restore-after-failure cases.

| # | Category | When | Primary depth source |
|---|---|---|---|
| 1 | `installation-startup` | Containers crash on `docker compose up`; healthchecks loop; port conflicts | Compose ps + per-service logs + `compose config` |
| 2 | `upgrade` | After `infrahub upgrade` or `helm upgrade`; branches stuck in `NEED_UPGRADE_REBASE` | `neo4j-admin server report` + 24h logs + branch list |
| 3 | `git-sync` | Repo state `Error`/`Unknown`; `CommitNotFoundError`; schemas not loaded from repo | Per-worker `/opt/infrahub/git` inspection + repo GraphQL + `.infrahub.yml` |
| 4 | `task-worker-pipeline` | Tasks stuck `RUNNING`/`MERGING`; worker CrashLoopBackOff; PC pipeline never completes | `task list --include-logs` + Prefect + RabbitMQ depth + all worker replicas |
| 5 | `schema-load` | `schema check` rejects file; `/api/schema/load` hangs; schema hash drift | `schema check` + `/api/schema/summary` + 30m server logs |
| 6 | `check-generator-transform` | Pipeline check red; `infrahubctl <kind>` raises; Jinja2 transform fails | `infrahubctl check/generator/render/transform` repro + source files + worker logs |
| 7 | `graphql-api` | HTTP 5xx; non-nullable field errors; timeouts | Echo query (`INFRAHUB_ECHO_GRAPHQL_QUERIES=true`) + 15m server logs + response body |
| 8 | `performance` | Slow UI, slow diff, OOM kills, browser hangs on large nodes | `docker stats` + Neo4j active queries + telemetry + host resources |
| 9 | `auth-permissions` | OAuth/OIDC login fails; default role can't create PC; JWT mismatch | Redacted SSO env + `CoreAccount` GraphQL + 30m auth-filtered logs |
| 10 | `branch-merge` | Branch stuck `MERGING`/`DELETING`; failed merge leaves partial state | `branch list` + direct Neo4j peek + activity log export prompt |

When the user is unsure of category, the skill falls
through to **everything** mode — runs every
category's depth collection. Heavier bundle, but never
misses the root cause's data.

## Baseline (always collected)

Stored under `bundle/baseline/`:

- **Versions:** `infrahubctl version`, `infrahubctl
  info --detail`, `docker --version`,
  `docker compose version`, `helm version`,
  `kubectl version`, `python3 --version`, `uname -a`
- **Server state:** `/api/config` (cross-check
  version + edition)
- **Deployment topology:** image SHAs, replica
  counts, container/pod status
- **Host:** OS, CPU cores, free memory, disk usage
- **Config:** `.infrahub.yml`, `infrahub.toml`,
  `docker compose config` (redacted),
  `helm get values --all` (redacted)
- **Repo state:** copy of `schemas/` + sha256
  manifest
- **Live state:** `branches.json`, `repositories.txt`,
  `schema-kinds.txt`, `recent-tasks.json`,
  `telemetry.json` (unless opted out)
- **Logs:** 24h logs from every service, one file
  per replica

Kubernetes equivalents are documented in
`reference.md` (service-name map is identical;
commands differ).

## Bundle layout

```
infrahub-diagnostics-YYYYMMDD-HHMMSS/
├── README.md                # what's here, how to reproduce, redaction notes
├── manifest.yml             # see schema below
├── flags.yml                # deterministic flag checks that fired
├── redaction-report.txt     # what was stripped and where
├── baseline/
│   ├── versions.yml
│   ├── api-config.json
│   ├── deployment.yml
│   ├── host.yml
│   ├── config/
│   ├── schemas/             # + schemas.sha256
│   ├── state/
│   └── logs/                # one file per replica
├── category/
│   └── <category-name>/
├── repro/                   # user-provided minimal repro
│   ├── steps.md
│   ├── failing.gql          # graphql-api only
│   ├── schemas/             # schema-load only
│   └── runs/                # output of infrahubctl repro commands
└── user-input/
    ├── questions-answered.md   # mirrors upstream bug-report template
    ├── screenshots/
    └── browser-har.har         # UI bugs only
```

### `manifest.yml` schema (key fields)

```yaml
bundle_version: "1.0"
generated_at: "2026-05-30T12:00:00Z"
skill_version: "<infrahub-skills plugin version>"
infrahub:
  version: "1.9.6"           # from /api/config
  edition: "community"
  using_default_security_key: false   # see Tier-1 redaction below
  using_default_init_token: false
deployment:
  topology: "docker-compose"
  worker_replicas: 2
  image_shas:
    infrahub-server: "sha256:..."
    task-worker: "sha256:..."
host:
  os: "Linux 6.x"
  cpu_cores: 8
  memory_gb: 16
problem:
  # Mirrors opsmill/infrahub bug-report template
  component: "Git Integration"
  current_behavior: "..."
  expected_behavior: "..."
  steps_to_reproduce: "..."
  error_message: "..."
  first_observed: "2026-05-29"
  reproducible: true
  impact: "blocker"
  category: "git-sync"
collected:
  baseline: true
  category_dirs: ["git-sync"]
  repro_included: true
  multi_replica_coverage: true
redaction:
  applied: true
  rules_version: "1.0"
  files_touched: 47
  replacements: 192
  user_review_completed: true
  user_choices:
    public_ips: "redact-all"
    hostnames: "keep"
    customer_strings: "redact-all"
```

## Redaction policy

### Tier 1 — Automatic

Applied to every text/YAML/JSON file in the bundle.
Logged in `redaction-report.txt` with file + line for
every replacement.

| Pattern | Replacement |
|---|---|
| Env keys matching `(PASSWORD\|SECRET\|TOKEN\|CLIENT_SECRET\|API_KEY\|AWS_SECRET_ACCESS_KEY\|DSN\|AUTH)`, case-insensitive | `***REDACTED:env-key***` |
| URL credentials `https?://user:pass@` | `https://***REDACTED***@` |
| JWT shapes (three base64 segments dot-joined) | `***REDACTED:jwt***` |
| AWS access keys `AKIA[0-9A-Z]{16}` + 40-char Base64 secret | `***REDACTED:aws***` |
| Private-key blocks (`-----BEGIN ... PRIVATE KEY-----`) | Stripped entirely |
| UUIDs adjacent to `INFRAHUB_INITIAL_ADMIN_TOKEN` / `INFRAHUB_INITIAL_AGENT_TOKEN` | `***REDACTED:init-token***` |

### Tier 2 — User review gate

After Tier 1 runs, before bundle is finalized. Skill
prints a one-screen summary:

- N files touched, M replacements by category
- Sample of distinct IPs (top 10 RFC1918 + top 10
  public)
- Sample of distinct hostnames in logs / GraphQL
  responses
- Sample of distinct customer/device-looking strings
  from `CoreAccount` + schema-export top values
- All webhook-looking URLs (Slack, Discord,
  PagerDuty, custom)

For each sample group the user picks `keep`,
`redact-all`, or `case-by-case`. Choice + counts go
to `manifest.yml`.

### Diagnostic-signal flags (not values)

`INFRAHUB_SECURITY_SECRET_KEY` and
`INFRAHUB_INITIAL_ADMIN_TOKEN` defaults are
diagnostic — multi-pod JWT bugs ([#8925](https://github.com/opsmill/infrahub/issues/8925))
hinge on whether the defaults are in use. The manifest
records `using_default_security_key: true/false` by
hash comparison; the value itself is always redacted.

## Flag checks

Deterministic only. Written to `flags.yml` after
collection. Never claim diagnosis — only hints.

Each entry:

```yaml
- id: <check-id>
  severity: info | warning
  evidence:
    file: baseline/logs/task-worker-1.log
    line: 4521
    excerpt: "CommitNotFoundError: ..."
  related_issues: [9036, 8930]
  hint: "Multi-worker git race; expert should check ..."
```

### v1 catalog (15 checks)

| ID | Check |
|---|---|
| `using-default-security-key` | `INFRAHUB_SECURITY_SECRET_KEY` matches the compose default |
| `using-default-init-token` | `INFRAHUB_INITIAL_ADMIN_TOKEN` matches the compose default |
| `worker-crashloop` | Any task-worker has restart count > 3 in 1h |
| `branch-stuck-merging` | Any branch with `status: MERGING` for > 10 min |
| `branch-needs-rebase` | Any branch in `NEED_UPGRADE_REBASE` |
| `repo-error` | Any `CoreGenericRepository` with `operational_status != "operational"` |
| `schema-hash-drift` | `/api/schema/summary` returns different hash per worker |
| `n-1-upgrade-violation` | `versions.yml` shows skipped versions vs. previous backup |
| `rabbit-queue-backlog` | Any RabbitMQ queue depth > 100 |
| `prefect-many-failed-runs` | > 5 FAILED runs in last hour |
| `oom-in-logs` | "OOMKilled" / "OutOfMemoryError" in logs |
| `db-tx-memory-limit` | "Transaction memory limit reached" |
| `commit-not-found` | "CommitNotFoundError" in worker logs |
| `git-permission-denied` | "fatal: ... Permission denied" in worker logs |
| `host-low-resources` | Free memory < 1GB or disk < 5GB |

The catalog is extensible — new checks add a row to
`flag-checks.md` and a function to the runner.

## Files in the skill

```
skills/infrahub-collecting-diagnostics/
├── SKILL.md
├── reference.md                 # commands per topology, env catalog, service-name map
├── examples.md                  # 2-3 walk-throughs (git-sync, upgrade, perf)
├── flag-checks.md               # full catalog + add-your-own guide
└── rules/
    ├── _sections.md
    ├── _template.md
    ├── workflow-user-gates.md
    ├── collection-read-only.md
    ├── multi-replica-coverage.md
    ├── redaction-tiers.md
    ├── deployment-detection.md
    ├── bundle-layout.md
    ├── manifest-template.md
    ├── flag-checks-deterministic.md
    └── cross-link-reporting-issues.md
```

No `templates/` directory — bundle is built from
inline string templates in the skill.

## Evaluations

Three tasks in `eval.yaml`, graders in
`graders/collecting-diagnostics/`:

| Task | What it tests |
|---|---|
| `git-sync-from-fresh-deployment` | Bundle has category=git-sync, baseline+category logs present, `commit-not-found` flag fires |
| `upgrade-with-stuck-branch` | Bundle has category=upgrade, `branch-needs-rebase` flag fires, neo4j-report present |
| `perf-investigation` | Bundle has category=performance, telemetry + neo4j-active-queries present, `oom-in-logs` flag fires if seeded |

Graders test bundle structure + flag JSON shape
against mocked command outputs (running real Infrahub
in CI is out of scope). Each grader:

1. Loads the skill's output bundle directory.
2. Asserts manifest fields, file presence, flag shape.
3. Returns `{"pass": true/false, "reason": "..."}`.

A rule-eval pairing checklist (per the
"Rule = Test" requirement in AGENTS.md) is enforced
in code review.

## Versioning

The skill's `metadata.version` will start at the
current plugin version (whatever
`.claude-plugin/plugin.json` is on `main` when the PR
opens) so that the unified version cadence is
preserved.

## Open follow-ups (post-v1)

- Bundle encryption + age/PGP optional wrapper
- Direct upload to a future OpsMill support endpoint
- Slack/Discord paste-format short-summary export
- Anonymizer mode (replace device names with
  `device-NNN` while preserving structure)

## References

- [Research report](agent transcript, 2026-05-30) —
  in-band research summary; not committed
- [opsmill/infrahub bug-report template](https://github.com/opsmill/infrahub/blob/main/.github/ISSUE_TEMPLATE/bug_report.yml)
- [opsmill/infrahub docker-compose.yml](https://github.com/opsmill/infrahub/blob/main/docker-compose.yml)
- [docs.infrahub.app — Troubleshooting (Emma)](https://docs.infrahub.app/emma/reference/troubleshooting)
- [docs.infrahub.app — Configuration reference](https://docs.infrahub.app/reference/configuration)
- [docs.infrahub.app — Backup & restore](https://docs.infrahub.app/deploy-manage/maintain-upgrade/database-backup/backup-and-restore)
- [docs.infrahub.app — Upgrade overview](https://docs.infrahub.app/deploy-manage/maintain-upgrade/upgrade/overview)
- [docs.infrahub.app — Telemetry](https://docs.infrahub.app/deploy-manage/run-observe/telemetry)
- [docs.infrahub.app — Tasks](https://docs.infrahub.app/deploy-manage/run-observe/tasks)
- Multi-worker race issues: [#9036](https://github.com/opsmill/infrahub/issues/9036),
  [#9293](https://github.com/opsmill/infrahub/issues/9293),
  [#9349](https://github.com/opsmill/infrahub/issues/9349)
- Multi-pod JWT issue: [#8925](https://github.com/opsmill/infrahub/issues/8925)
- Sibling skill (kept separate by policy):
  `skills/infrahub-reporting-issues/`
