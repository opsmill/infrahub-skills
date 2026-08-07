---
title: Sweep every service for the known signal classes
impact: CRITICAL
tags: triage, tracebacks, log-levels, oom
---

## Sweep every service for the known signal classes

Impact: CRITICAL

Scan the logs of **every** service directory under
`bundle/logs/` — server, task-worker, task-manager,
database, message-queue, cache — for each error
signal class, not just the service the user
complained about.

### Why it matters

Infrahub is a multi-service system: the service that
surfaces an error is frequently not the service that
caused it. A user reports "the UI throws 500s"
(server), while the cause sits in the database or
message-queue log. Sweeping only the reported
service produces a report about symptoms. The signal
classes are enumerable, so the sweep is cheap and
mechanical — there is no reason to sample.

### What to do

Grep each service's logs for these classes (exact
patterns in [reference.md](../reference.md)):

- **Python tracebacks** — `Traceback (most recent
  call last)` in server / task-worker / task-manager
  logs; capture the full block, the exception class,
  and the innermost `infrahub` frame.
- **Severity markers** — `ERROR`, `CRITICAL`,
  `FATAL`, `PANIC` lines (database and message-queue
  logs use their own formats — see reference).
- **Resource kills** — `OutOfMemoryError`,
  `OOMKilled`, `Killed`, heap/memory exhaustion.
- **Connection failures** — `Connection refused`,
  `timeout`, retry storms between services.

Record every hit with its bundle path, timestamp,
and the surrounding lines — these feed correlation
and issue matching.

### Compliant

```text
Sweep results:
- bundle/logs/server/: 41 ERROR lines (connection
  refused to database, 14:02-14:05), 1 traceback
- bundle/logs/database/: java.lang.OutOfMemoryError
  at 14:02:11
- bundle/logs/task-worker/: clean
- bundle/logs/message-queue/: clean
```

### Non-compliant

```text
The user said the UI throws 500s, so I checked
bundle/logs/server/ and found connection errors.
Root cause: the server cannot reach the database.
```

The sweep stopped at the symptom service; the
database OOM one directory over — the actual root —
was never read.

### Common mistakes

- Only reading the server log because the complaint
  was about the UI or the API.
- Grepping for `ERROR` only, missing Java-style
  (`OutOfMemoryError`) and container-level
  (`OOMKilled`) signals that use different formats.
- Recording matches without timestamps or paths,
  which makes the correlation step guesswork.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
