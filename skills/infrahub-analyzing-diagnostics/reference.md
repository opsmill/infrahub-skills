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

A Python traceback's most useful parts for matching:
the **exception class** (last line), the **message**
after the colon, and the **innermost frame whose
path contains `infrahub`** (frames in site-packages
below it belong to libraries).

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

One section per incident:

```markdown
## Incident <n>: <one-line summary> (<severity>)

- Window: <first signal> → <last signal>
- Root: <error> — <bundle path>
  > <quoted excerpt, 1-3 lines>
- Cascade: <downstream effects with paths>
- Known issue: <matched issue URL + state, or
  "no match (queries: ...)">
- Open questions: <what this bundle cannot answer,
  and which `infrahub-collect create` flags a next
  bundle would need>
- Recommendation: <next step — not executed here>
```

Severity scale: CRITICAL (service down / data at
risk), HIGH (feature broken, crash loop), MEDIUM
(degraded, recovering), LOW (noise worth noting).

## Docs

- [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
- [Infrahub architecture](https://docs.infrahub.app/overview/architecture)
- [opsmill/infrahub issues](https://github.com/opsmill/infrahub/issues)
