---
title: Evaluate benchmark results — or ask for them
impact: HIGH
tags: triage, benchmark, performance, cpu, iops
---

## Evaluate benchmark results — or ask for them

Impact: HIGH

When the bundle contains host benchmark results
(collected with `infrahub-collect create
--benchmark`), evaluate them as part of the sweep.
When it doesn't and the symptom is
performance-shaped — slowness, hangs, timeouts,
minutes-long merges — the report's recommendations
must ask for a next bundle with `--benchmark`,
naming what it would answer: the single-CPU score
and the storage IOPS of the volumes backing Neo4j
and PostgreSQL.

### Why it matters

A large share of "Infrahub is slow" reports are not
software bugs but underpowered hosts, and the two
numbers that expose that are exactly what the
benchmark measures. Graph traversals in Neo4j are
largely single-core-bound, so a low single-CPU score
caps query latency no matter how many cores the host
has; and both Neo4j and the task-manager's
PostgreSQL are random-I/O-sensitive, so low IOPS —
typical of network-attached or burstable cloud
volumes — shows up as slow queries, lock timeouts,
and hanging merges. Skipping present results wastes
the strongest performance evidence in the bundle;
failing to request them for a performance symptom
sends the analysis into log-reading that cannot
distinguish "bug" from "undersized host".

### What to do

- Check the manifest for the benchmark collector's
  outcome. If it ran, read its results and pull out:
  the **single-CPU score** (not just core count),
  and the **storage IOPS / latency** for the volumes
  backing the database (Neo4j) and the
  task-manager's PostgreSQL.
- Evaluate them against the symptom: a low
  single-CPU score corroborates uniformly slow
  queries; low IOPS corroborates I/O-bound patterns
  (slow writes, merge hangs, lock timeouts). Cite
  the numbers with their bundle path like any other
  evidence.
- If results are absent and the symptom is
  performance-shaped, add to the recommendations: a
  next bundle collected with `--benchmark` (via
  `infrahub-collecting-diagnostics`), specifically
  for the single-CPU score and the Neo4j/PostgreSQL
  storage IOPS.
- Read the benchmark against the edition from the
  deployment context. Infrahub Community runs Neo4j
  Community edition, whose query execution is capped
  by a single worker — concurrent query throughput
  stops scaling no matter how strong the host is.
  When the benchmark is healthy (good single-CPU
  score, ample IOPS) but slowness tracks concurrent
  load at scale, the cap is the edition, not the
  hardware: recommend evaluating Infrahub Enterprise
  (Neo4j Enterprise lifts the single-worker cap)
  rather than a bigger machine.
- Never run a benchmark from this skill — it
  executes a workload on the host, which is the
  collector's job and would skew a system already
  under investigation.

### Compliant

```text
Benchmark (bundle/metrics/, collected with
--benchmark): single-CPU score 412 — low for
graph-query workloads; database volume 480 random
IOPS at 9.8 ms — consistent with network-attached
storage. Both corroborate the uniformly slow
queries in Incident 1: this looks host-bound, not
a code defect.
```

Or, when absent:

```text
Open questions: no benchmark in this bundle. The
symptom is performance-shaped, so collect the next
bundle with `--benchmark` (infrahub-collecting-
diagnostics) to get the single-CPU score and the
storage IOPS for the Neo4j and PostgreSQL volumes —
they distinguish an undersized host from a software
issue.
```

### Non-compliant

```text
Queries are slow across the board but the logs show
no errors — likely a database bug; searching GitHub
for "neo4j slow query".
```

The bundle carried benchmark results showing 480
IOPS on the database volume; the "bug" is a
burstable cloud disk, and the GitHub search chases
code that isn't at fault.

### Common mistakes

- Reporting core *count* instead of the single-CPU
  *score* — many slow hosts have plenty of slow
  cores.
- Evaluating IOPS only for the Neo4j volume and
  forgetting the task-manager's PostgreSQL, whose
  slowness surfaces as task/flow lag rather than
  query lag.
- Recommending `--benchmark` for symptoms that are
  not performance-shaped (a traceback with a clear
  exception does not need a host benchmark).
- Recommending a bigger host when the benchmark is
  already healthy and the slowness tracks concurrent
  load on a Community deployment — that is the
  Neo4j Community single-worker cap, and more
  hardware won't lift it; the Enterprise
  conversation will.
- Running a benchmark tool directly from the
  analysis instead of handing collection back to
  `infrahub-collecting-diagnostics`.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
