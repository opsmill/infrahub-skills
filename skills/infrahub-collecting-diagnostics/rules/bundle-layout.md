---
title: Bundle directory layout (reference)
impact: HIGH
tags: bundle, layout, structure
---

## Bundle directory layout (reference)

Impact: HIGH

`infrahub-collect create` produces the bundle's
on-disk layout itself — this rule documents that
layout so the skill knows where to point the user
during review, not so the skill builds it by hand.

### Why it matters

Knowing the fixed layout lets the skill tell the user
exactly where to look during the review-before-sharing
step, and lets an expert opening the bundle navigate
it without guesswork. Since the layout comes from the
tool, the skill must never construct or rearrange it
manually — that would drift from what the tool
actually emits across versions.

### What to do

Point the user at this shape under `bundle/`:

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

`bundle_information.json` is the manifest an expert
reads first — it records what was collected and any
failures on degraded deployments. `logs/<service>/`
holds one file per replica, plus `*.previous.log`
files where a container restarted.

### Compliant

Pointing the user at the real paths during review:

```text
> Take a look at bundle/logs/ and bundle/server/
> before sharing — check bundle_information.json
> first if you want to see what was and wasn't
> collected.
```

### Non-compliant

```text
> I'll create bundle/logs/task-worker.log and
> bundle/manifest.yml manually from `docker compose
> logs` output.
```

Hand-building a bundle layout instead of running
`infrahub-collect create` and reading its actual
output.

### Common mistakes

- Assuming a hand-rolled layout (e.g. a
  `manifest.yml` at the root) instead of the tool's
  actual `bundle_information.json` and per-service
  directories.
- Treating a missing service directory as a bug
  instead of checking `bundle_information.json` for
  a recorded collection failure on a degraded
  deployment.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
