---
title: Analysis is read-only — no mutations, no fixes
impact: CRITICAL
tags: scope, read-only, no-mutations
---

## Analysis is read-only — no mutations, no fixes

Impact: CRITICAL

This skill reads files from an already-collected
bundle and searches GitHub. It never touches the
running deployment — no restarts, no
`docker`/`kubectl` mutations, no config edits, no
"quick fixes" — and it does not re-collect logs from
the live system.

### Why it matters

The bundle exists precisely so analysis can happen
without touching a degraded production system. A
restart destroys the very state an OpsMill engineer
may still need (crash loops, container filesystem,
queue depth), can turn a partial outage into a full
one, and invalidates the bundle as a faithful
snapshot. The same boundary that makes
`infrahub-collect` safe to run — read-only by design
— makes this skill safe to run after it.

### What to do

- Operate on bundle files (`Read`, `Grep`, `Glob`)
  and GitHub search; write only the report.
- Put remediation in the report as
  *recommendations*, each grounded in a finding —
  for the user or OpsMill support to act on.
- If live-state questions come up mid-analysis
  ("is it still crashing *now*?"), answer from the
  bundle or mark as an open question. Do not run
  live `docker`/`kubectl` commands "just to check" —
  a fresh bundle via
  `infrahub-collecting-diagnostics` is the way to
  get newer state.

### Compliant

```text
Recommendation (do not execute from this analysis):
the database container's heap limit appears
undersized for this dataset — raising it is a
change for your ops process, ideally after OpsMill
support confirms F1.
```

### Non-compliant

```text
The database OOM'd — restarting it now to confirm:
docker compose restart database
```

Mutates a degraded production system mid-analysis
and destroys the crash state support may need.

### Common mistakes

- "Verifying" a hypothesis with a restart or
  container mutation instead of stating the
  hypothesis with its supporting evidence.
- Editing compose files or Helm values as part of
  the analysis output instead of writing a
  recommendation.
- Running live `docker compose logs`/`kubectl logs`
  to supplement a stale bundle instead of handing
  back to `infrahub-collecting-diagnostics`.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
