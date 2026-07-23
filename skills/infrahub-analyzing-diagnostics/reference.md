# Reference — analyzing a diagnostic bundle

Signal patterns, per-service log notes, manifest
fields, and GitHub search recipes. The workflow in
[SKILL.md](SKILL.md) links here for the exact
commands at each step.

## Bundle layout (recap)

The layout is produced by `infrahub-collect create`
and documented authoritatively in
[../infrahub-collecting-diagnostics/reference.md](../infrahub-collecting-diagnostics/reference.md):

```text
bundle/
├── bundle_information.json   # manifest: what was collected, what failed
├── logs/
│   └── <service>/            # one file per replica
│       └── *.previous.log    # present after container restarts
├── database/
├── message-queue/
├── cache/
├── task-worker/
├── task-manager/
├── server/
└── metrics/
```

Analysis order: `bundle_information.json` →
`logs/*/` (including every `*.previous.log`) → the
per-service state directories (`server/`,
`database/`, ...) as findings demand.

## Manifest

`bundle_information.json` records the deployment
that was collected and the outcome per collector.
Read it for:

- **Deployment/topology info** — Compose project or
  K8s namespace; anchors which services to expect.
- **Collector outcomes** — anything that failed is a
  finding (see
  [rules/workflow-manifest-first.md](rules/workflow-manifest-first.md)).
- **Collection timestamp** — bounds the timeline;
  errors near the end of a log may continue past the
  bundle's horizon.

## Deployment context

Anchor these three facts before triage and put them
in the report's first lines (see
[rules/workflow-deployment-context.md](rules/workflow-deployment-context.md)):

- **Version and edition** — from `bundle/server/`
  state or the server log's startup banner. The
  version drives the known-issue conclusion: fix
  version newer than the running version → upgrade;
  running version already at/past the fix →
  unconfirmed match / possible regression. The
  edition (Community vs Enterprise) drives
  scale-related conclusions — see the edition cap
  under Benchmark results.
- **Topology** — Compose project or K8s namespace,
  from the manifest. Several known failure patterns
  (below) are Kubernetes-specific.
- **Size** — replica counts from the per-replica
  files under `bundle/logs/<service>/`. Multi-replica
  API servers have their own failure pattern (shared
  object storage).

## Signal sweep — grep patterns

Run across **all** of `bundle/logs/` (`-r`), never a
single service. Case-insensitive where formats vary:

```bash
# Python tracebacks (server, task-worker, task-manager)
grep -rn "Traceback (most recent call last)" bundle/logs/

# Severity markers (all services)
grep -rniE "\b(error|critical|fatal|panic)\b" bundle/logs/

# Resource kills / OOM (database is Java; container runtime may log OOMKilled)
grep -rniE "outofmemory|oomkilled|out of memory|killed" bundle/logs/

# Connection failures and retry storms
grep -rniE "connection (refused|reset|closed)|timed? ?out|retry" bundle/logs/

# Restart evidence
find bundle/logs -name "*.previous.log"
```

For each hit, keep: bundle path, timestamp, and 2-3
surrounding lines (`grep -B2 -A6` around tracebacks
to capture the exception line below the frames).

## Per-service log notes

| Service | Runtime | What its errors look like |
| ------- | ------- | ------------------------- |
| server | Python (FastAPI/GraphQL) | Python tracebacks; structured lines with levels; GraphQL errors may embed the operation name |
| task-worker / task-manager | Python (Prefect-based) | Python tracebacks; task/flow retry messages; killed workers often only visible in `*.previous.log` |
| database | Neo4j (Java) | `java.lang.*` exceptions, `OutOfMemoryError: Java heap space`, GC/stop-the-world warnings |
| message-queue | RabbitMQ / NATS | connection churn, channel errors, memory watermarks |
| cache | Redis / Valkey | `WARNING`/`# ...` lines, persistence and memory warnings |

The task-manager is a Prefect server with its own
dependency tail — a PostgreSQL database and Redis —
so task-manager errors frequently originate there
rather than in Infrahub code; read its log with that
in mind. Task and worker logs are also viewable in
the Infrahub UI's task history (internal system
tasks excepted) — a useful fallback when the
bundle's log window is truncated, and a way for the
user to check state newer than the bundle.

A Python traceback's most useful parts for matching:
the **exception class** (last line), the **message**
after the colon, and the **innermost frame whose
path contains `infrahub`** (frames in site-packages
below it belong to libraries).

## Benchmark results

When the manifest shows `create --benchmark` ran,
the bundle carries host benchmark results — evaluate
them as evidence, not an afterthought (see
[rules/triage-benchmark-results.md](rules/triage-benchmark-results.md)):

- **Single-CPU score** — graph traversals in Neo4j
  are largely single-core-bound; a low score caps
  query latency regardless of core count. Report the
  score, not the core count.
- **Storage IOPS / latency** for the volumes backing
  Neo4j *and* the task-manager's PostgreSQL — both
  are random-I/O-sensitive. A few hundred IOPS with
  high latency is the signature of network-attached
  or burstable cloud storage and corroborates slow
  writes, lock timeouts, and hanging merges.

Low values + performance symptom → the incident is
likely host-bound: say so, and aim the
recommendation at sizing/storage rather than a
GitHub search. No benchmark + performance symptom →
the recommendations must include a next bundle with
`--benchmark` via `infrahub-collecting-diagnostics`.

**Healthy values + slowness under concurrent load →
check the edition.** Infrahub Community runs Neo4j
Community edition, whose query execution is capped
by a single worker: concurrent throughput stops
scaling regardless of host strength. On a Community
deployment at scale, that pattern is the edition
cap, not the hardware — recommend evaluating
Infrahub Enterprise (Neo4j Enterprise lifts the
cap) instead of a bigger machine.

## Correlation heuristics

- Dependency order (lower = more upstream):
  database / message-queue / cache → server →
  task-manager → task-worker. Cascades flow
  downstream; root candidates sit upstream and fail
  earliest.
- Connection errors name their peer — `Connection
  refused` to the database points the incident at
  the database, not at the erroring service.
- A restart timestamp (from `*.previous.log` tails)
  anchors the incident window.
- Log clocks are the container's own; small skews
  between services are normal. Cluster on windows,
  not exact equality.
- The task-manager (Prefect) adds a side-branch to
  the dependency order: it depends on its own
  PostgreSQL and Redis. Worker symptoms (tasks not
  starting, flows stuck) can root in that branch
  without the main database or message-queue showing
  anything — check task-manager logs for
  Postgres/Redis connection errors before concluding
  the workers themselves are at fault.

## Known failure patterns

Field-proven symptom-to-cause mappings. Check these
before searching GitHub — when one fits, the search
gets targeted (or becomes unnecessary) and the
report can point at configuration instead of code.
Each still needs bundle evidence before it goes in
the report as more than a hypothesis.

| Symptom | Likely cause | Where to look in the bundle |
| ------- | ------------ | --------------------------- |
| Triggers or computed attributes not firing (K8s) | Prefect background services not running — commonly disabled by hand-edited Helm values; the chart's env-var *list* is overridden wholesale by Helm, not merged | Manifest collector outcomes and `bundle/logs/task-manager/`: missing/empty background-service activity; no trigger-execution lines around the symptom window |
| Merge or proposed-change crashes midway, later merges hang | Long-lived lock left behind (deadlock); the periodic cleanup task should clear it and may itself be stuck | `bundle/cache/` state for old locks; `bundle/logs/task-manager/` for the cleanup task's runs around the window |
| Tasks stuck in RUNNING long after activity stopped | Stale task entries surviving a worker crash/restart | `*.previous.log` restart evidence for the workers; task-manager log around the worker's death. Remediation to *recommend* (never run from analysis): the `infrahub-taskmanager` CLI can delete stale RUNNING tasks |
| Data or repositories gone after a pod restart (K8s) | Storage persistence disabled in the deployment values | Restart evidence plus post-restart logs showing empty/initialized state where data existed before |
| Artifact/storage errors only on multi-replica API servers | No shared object storage (S3-compatible) configured — replicas can't see each other's artifacts | Replica count under `bundle/logs/server/`; storage-backend errors appearing on some replicas but not others |
| Uniformly slow queries/UI with clean logs | Undersized host: low single-CPU score, or low-IOPS storage backing Neo4j/PostgreSQL (network-attached or burstable volumes) | Benchmark results when collected (`--benchmark`); if absent, the next bundle needs that flag before concluding anything |
| Slowness that tracks concurrent load at scale, benchmark healthy (Community edition) | Neo4j Community's single-worker query execution caps concurrent throughput — more hardware won't lift it | Edition + version in the deployment context; healthy benchmark numbers; slowness correlating with user/automation concurrency. Recommendation: evaluate Infrahub Enterprise |

When a pattern fits but its confirming evidence sits
outside the bundle (Helm values, live pod listing,
Redis lock listing), report the hypothesis with what
the bundle *does* show and name the missing check as
an open question for the user or the expert.

## GitHub issue search

```bash
# Primary — both open and closed, stable keywords only
gh search issues --repo opsmill/infrahub --state all "<ExceptionClass> <stable message words>"

# Second pass — synonyms / alternate fragment
gh search issues --repo opsmill/infrahub --state all "<module or symptom keywords>"
```

Key construction (see
[rules/match-stable-search-keys.md](rules/match-stable-search-keys.md)):
keep the exception class and constant message words;
strip UUIDs, branch names, hostnames, IPs, file
paths, timestamps, and object names unique to the
deployment.

Fallbacks, in order: a GitHub MCP tool if the
environment has one; otherwise hand the user the URL:

```text
https://github.com/opsmill/infrahub/issues?q=is%3Aissue+<keywords>
```

Nearly all platform symptoms belong in
`opsmill/infrahub`. Only search a sub-repo when the
traceback is unambiguous about it (e.g.
`infrahub_sdk/` frames → `opsmill/infrahub-sdk-python`)
— and repo *routing* for filing purposes stays with
`infrahub-reporting-issues`.

## Findings report shape

Open the report with the deployment line, then one
section per incident:

```markdown
# Findings — <project/namespace> bundle (collected <ts>)

Deployment: Infrahub <version> (<edition>),
<topology>, <replica counts>. Manifest:
<collectors ok/failed>.

## Incident <n>: <one-line summary> (<severity>)

- Window: <first signal> → <last signal>
- Root: <error> — <bundle path>
  > <quoted excerpt, 1-3 lines>
- Cascade: <downstream effects with paths>
- Known issue: <matched issue URL + state; when it
  names a fix version, the comparison against the
  running version — or "no match (queries: ...)">
- Open questions: <what this bundle cannot answer;
  whether the symptom reproduces on demand and when
  it last did; which `infrahub-collect create` flags
  a next bundle would need>
- Recommendation: <next step — not executed here>
```

Severity scale: CRITICAL (service down / data at
risk), HIGH (feature broken, crash loop), MEDIUM
(degraded, recovering), LOW (noise worth noting).

## Docs

- [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
- [Infrahub architecture](https://docs.infrahub.app/overview/architecture)
- [opsmill/infrahub issues](https://github.com/opsmill/infrahub/issues)
