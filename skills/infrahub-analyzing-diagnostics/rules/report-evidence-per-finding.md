---
title: Every finding cites bundle evidence
impact: CRITICAL
tags: report, evidence, findings, unknowns
---

## Every finding cites bundle evidence

Impact: CRITICAL

Each finding in the report carries its evidence: the
bundle file path it came from and a short quoted
excerpt. Conclusions the bundle cannot support are
labeled hypotheses or unknowns — never stated as
fact.

### Why it matters

The report's audience — the user, a GitHub issue
thread, or an OpsMill engineer — will act on it.
An engineer receiving "the database ran out of
memory (bundle/logs/database/database-1.log, line
2141)" can verify in seconds and move on; one
receiving "the database probably ran out of memory"
with no pointer has to redo the entire sweep. Worse,
a confident-sounding but unsupported root cause
sends everyone down the wrong path — a wrong
diagnosis costs more than no diagnosis.

### What to do

- For every finding: severity, the bundle path(s),
  and a 1-3 line quoted excerpt.
- Keep the causal chain explicit: which evidence
  supports which conclusion.
- When the bundle cannot answer something (missing
  collector, log window too short, no error before
  a crash), write it as an open question — and, if
  more collection would answer it, say which
  `infrahub-collect create` flags the next bundle
  needs (via `infrahub-collecting-diagnostics`).
- Never pad the report with a guessed root cause to
  look complete.

### Compliant

```text
Finding F2 (HIGH): task-worker-1 crashed at 14:03:07.
Evidence: bundle/logs/task-worker/task-worker-1.previous.log
(tail): "ERROR ... database connection timeout
(attempt 12/12)". Cause of the timeout: see F1
(database OOM). Not determinable from this bundle:
what drove heap usage before the OOM — a next bundle
with --include-queries would show the active
queries.
```

### Non-compliant

```text
The task-worker crashed because a query with a
missing index exhausted the database heap. Add an
index to fix it.
```

No path, no excerpt, and a root cause (missing
index) that nothing in the bundle establishes.

### Common mistakes

- Summarizing "many errors in the server log"
  without one concrete quoted line.
- Promoting a plausible hypothesis to a stated root
  cause because the report "needs" a conclusion.
- Burying what could *not* be determined instead of
  listing it as an open question with the collection
  flags that would answer it.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
