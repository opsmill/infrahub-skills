---
title: Read the manifest before any log
impact: CRITICAL
tags: workflow, manifest, bundle-information
---

## Read the manifest before any log

Impact: CRITICAL

Open `bundle/bundle_information.json` before reading
a single log line. It is the bundle's table of
contents: which deployment was collected, which
collectors succeeded, and — most importantly — which
failed.

### Why it matters

`infrahub-collect create` exits 0 even when
collectors fail on a degraded deployment; the
failures are recorded in the manifest, not raised as
errors. A service whose logs are missing is often
the very service that is down. Skipping the manifest
turns that strongest-available signal into a blind
spot, and leads to wasted time grepping directories
that were never populated. The manifest also scopes
the analysis honestly: conclusions drawn from a
partial bundle must say so.

### What to do

- Read `bundle/bundle_information.json` first.
- List which collectors succeeded and which failed.
- Promote every recorded collection failure to a
  finding (e.g. "task-worker logs could not be
  collected — the container may be down"), to be
  correlated with signals from the services that
  were collected.
- State in the report when analysis ran on a partial
  bundle, and which services are missing.

### Compliant

```text
Manifest (bundle/bundle_information.json): 7/8
collectors succeeded. `message-queue` log collection
failed ("container not running") — treated as
finding F1 and correlated with the connection
errors in bundle/logs/server/.
```

### Non-compliant

```text
I grepped bundle/logs/ for errors. The
message-queue directory is empty, so the message
queue was healthy.
```

An empty directory means collection failed or was
skipped — the manifest says which. It never means
"healthy".

### Common mistakes

- Treating a missing or empty service directory as
  proof the service was fine, instead of checking
  the manifest for a recorded collection failure.
- Reporting findings from a partial bundle without
  disclosing which services were never collected.
- Re-running collection by hand to "fill the gap" —
  if more data is needed, that is a hand-off to
  `infrahub-collecting-diagnostics`.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
