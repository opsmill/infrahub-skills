---
title: Treat *.previous.log as restart evidence
impact: HIGH
tags: triage, restarts, previous-log, crash
---

## Treat *.previous.log as restart evidence

Impact: HIGH

A `*.previous.log` file under
`bundle/logs/<service>/` exists only because that
container restarted — `infrahub-collect` captures
the pre-restart log alongside the current one. Its
presence is itself a finding, and its tail is where
the crash cause lives.

### Why it matters

The current log of a restarted container starts
*after* the crash — it often looks healthy, which is
exactly what makes restarts easy to miss. The last
lines the process wrote before dying (the fatal
exception, the OOM kill, the panic) are in the
previous log's tail. Skipping `*.previous.log` files
means reporting "task-worker logs look clean" about
a service that died minutes earlier.

### What to do

- Glob for `*.previous.log` across all of
  `bundle/logs/` before reading current logs.
- Report each one as restart evidence for its
  service, with a count when there are several
  replicas.
- Read the **tail** of each previous log first — the
  crash cause is at the end, not the beginning.
- Feed the crash time into the correlation step: the
  restart usually anchors the incident timeline.

### Compliant

```text
bundle/logs/task-worker/task-worker-1.previous.log
exists → task-worker-1 restarted. Tail shows the
worker was killed at 14:03:07 after repeated
database connection timeouts — consistent with the
database OOM at 14:02:11.
```

### Non-compliant

```text
bundle/logs/task-worker/task-worker-1.log shows
normal startup messages. task-worker: healthy.
```

The current log starts after the restart; the
`.previous.log` sitting next to it was never opened.

### Common mistakes

- Reading only `<service>-1.log` and never globbing
  for `*.previous.log`.
- Reading the previous log from the top and stopping
  before the tail, where the fatal error actually is.
- Reporting the restart without a timestamp, so it
  cannot be correlated with the root incident.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
