---
title: Match create flags to the reported symptom
impact: HIGH
tags: create, flags, symptom
---

## Match create flags to the reported symptom

Impact: HIGH

Start with plain `infrahub-collect create` and add
only the flags that match the symptom captured in
step 1. Don't pile on every flag by default.

### Why it matters

Some flags trade off collection time, bundle size,
or data sensitivity for extra diagnostic depth.
`--include-queries` can capture customer data (it's
off by default for that reason), and `--benchmark`
pulls an extra OpsMill image and runs a workload —
useful for performance triage, wasted effort for a
git-sync error. Matching flags to the actual symptom
keeps the bundle focused and keeps collection time
and data exposure proportionate to the problem.

### What to do

| Symptom | Add flag |
| ------------------------------------ | ------------------- |
| Performance / OOM / slow UI | `--benchmark` |
| Slow or failing DB operations | `--include-queries` |
| Support asks to reproduce the issue | `--include-backup` |
| Multiple Compose projects on host | `--project=<name>` |
| Custom K8s namespace / labels | `--k8s-namespace=<ns>` |
| Custom output location | `--output-dir=<path>` |

`--include-queries` may capture customer data in
query text — it's off by default; only add it when
DB behavior is the actual symptom. `--benchmark`
pulls an OpsMill benchmark image; if it can't be
pulled (e.g. airgapped), the tool skips that step
with a warning rather than failing the whole run.

The default output directory is `./infrahub_bundles`
if `--output-dir` isn't set.

### Compliant

```bash
# Slow UI / suspected OOM
infrahub-collect create --benchmark

# DB queries timing out
infrahub-collect create --include-queries

# Support asked for a reproducer
infrahub-collect create --include-backup

# Nothing unusual reported yet
infrahub-collect create
```

### Non-compliant

```bash
# Git-sync error, but every flag added "just in case"
infrahub-collect create --benchmark --include-queries --include-backup
```

### Common mistakes

- Adding every flag by default instead of matching
  the reported symptom — this needlessly extends
  collection time and, for `--include-queries`,
  needlessly risks capturing customer data.
- Adding `--include-queries` for a symptom that has
  nothing to do with database behavior.
- Forgetting `--project`/`--k8s-namespace` when
  `environment detect` reports ambiguity, causing
  `create` to target the wrong deployment.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
