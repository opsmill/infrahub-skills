---
title: Correlate signals into incidents before reporting
impact: HIGH
tags: correlate, incidents, root-cause, cascade
---

## Correlate signals into incidents before reporting

Impact: HIGH

Group the raw signals from the triage sweep by
timestamp and causal chain into **incidents** — one
per underlying problem — and within each incident
distinguish the root error from the cascade errors
it triggered downstream.

### Why it matters

A single database OOM produces dozens of secondary
errors: server connection refusals, task-worker
retry storms, worker restarts. Reported flat, that
reads as "three broken services and 50 errors" and
sends the user (or the GitHub search, or OpsMill
support) chasing symptoms. Grouped, it reads as "one
incident: database OOM at 14:02, cascading to server
and task-worker" — one thing to investigate, one
issue to search for.

### What to do

- Order all signals on one timeline; cluster signals
  within the same time window.
- Within a cluster, identify the earliest failure in
  the dependency chain as the **root candidate**
  (database and message-queue sit below server and
  workers; a service that died before the others
  erred is upstream of them).
- Label the rest of the cluster **cascade** and say
  which root explains it (connection errors point at
  the peer that went away; retry storms follow
  outages).
- Signals that no cluster explains stay separate
  incidents — do not force everything into one
  story.
- Issue matching (see
  [match-stable-search-keys.md](match-stable-search-keys.md))
  runs on the root error, not on cascade noise.

### Compliant

```text
Incident 1 (14:02-14:05):
- Root: database OOM — bundle/logs/database/,
  java.lang.OutOfMemoryError at 14:02:11
- Cascade: 41 server connection errors
  (14:02:19-14:05:40); task-worker-1 killed and
  restarted at 14:03:07 (.previous.log)
```

### Non-compliant

```text
Findings: database has an OOM error. The server has
41 connection errors. The task-worker restarted.
Three problems found — consider searching GitHub
for "connection refused".
```

Three symptoms of one incident reported as three
problems — and the GitHub search targets the noise
instead of the root.

### Common mistakes

- Counting error lines instead of grouping them —
  41 identical connection errors are one cascade
  edge, not 41 findings.
- Picking the loudest error (most lines) as the
  root instead of the earliest failure in the
  dependency chain.
- Forcing unrelated signals into the main incident
  to tell a cleaner story; unexplained signals stay
  separate and are reported as such.

Reference: [Infrahub architecture](https://docs.infrahub.app/overview/architecture)
