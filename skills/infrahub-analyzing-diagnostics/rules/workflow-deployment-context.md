---
title: Establish deployment context before triage
impact: HIGH
tags: workflow, version, topology, deployment
---

## Establish deployment context before triage

Impact: HIGH

Right after the manifest, extract the deployment
context from the bundle — the running Infrahub
version, the topology (Docker Compose or
Kubernetes), and the rough size (replica counts per
service) — and put it at the top of the findings
report.

### Why it matters

The version decides how every later finding is
interpreted. A large share of reported problems are
already known and already fixed — a matched GitHub
issue closed with "fixed in X.Y.Z" resolves the
whole analysis to "upgrade" *only if* the bundle's
running version is older than the fix; if the
running version already includes the fix, the same
match means the opposite (not that issue, or a
regression worth flagging). Without the version in
hand, issue matching produces links but no
conclusion. Topology and size matter the same way:
several failure patterns are specific to Kubernetes
deployments or to multi-replica setups, and an
expert reading the report needs that context in the
first lines, not reverse-engineered from log paths.

### What to do

- Extract the running version — and the edition,
  Community or Enterprise — from the bundle:
  `bundle/server/` state, or the server log's
  startup banner. If either cannot be determined,
  say so explicitly rather than guessing. The
  edition matters for performance findings:
  Community's database layer is capped by Neo4j
  Community's single-worker execution, so
  scale-related conclusions differ by edition.
- Extract topology (Compose project vs K8s
  namespace) from the manifest, and replica counts
  from the per-replica log files under
  `bundle/logs/<service>/`.
- Open the findings report with a deployment line:
  version, topology, replicas.
- When a matched GitHub issue names a fix version,
  compare it against the running version and state
  the conclusion: older than the fix → upgrade
  resolves it; already at or past the fix → not this
  issue, or a regression — treat the match as
  unconfirmed.

### Compliant

```text
Deployment: Infrahub 1.2.4, docker-compose project
infrahub-prod, 1 server / 2 task-worker replicas
(bundle/bundle_information.json, bundle/server/).

Known issue: #5710 (closed — fixed in 1.2.2) looks
similar, but this deployment already runs 1.2.4, so
the match is unconfirmed — possibly a regression;
worth noting in the hand-off rather than advising an
upgrade.
```

### Non-compliant

```text
Found closed issue #5710 (fixed in 1.2.2) matching
the traceback — upgrade to fix it.
```

No running version established: if the deployment
already runs 1.2.4, "upgrade" is a dead end and the
real signal (possible regression) is lost.

### Common mistakes

- Advising an upgrade to a matched issue's fix
  version without checking the bundle's running
  version first.
- Burying version and topology mid-report instead
  of the first lines — the expert reading the
  hand-off needs them before any finding.
- Guessing the version from image tags or file
  paths when the bundle doesn't state it — mark it
  undetermined and list it as an open question.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
