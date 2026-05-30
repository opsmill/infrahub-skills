---
title: Bundle directory layout
impact: HIGH
tags: bundle, layout, structure
---

## Bundle directory layout

Impact: HIGH

The diagnostic bundle has a fixed on-disk shape so
an expert opening it for the first time can navigate
it without instructions. Required files always sit at
the root; optional sections appear only when they
apply.

### Why it matters

Experts triage many bundles in a week. A
predictable layout means they read `README.md` and
`manifest.yml` first, then drill into the directory
they need. Empty directories or missing required
files break the contract and force the expert to
re-derive what is actually present, which costs
their time and risks them missing something the
collector did capture.

### What to do

Produce this tree (paths verbatim from the spec):

```text
infrahub-diagnostics-YYYYMMDD-HHMMSS/
├── README.md                # what's here, how to reproduce, redaction notes
├── manifest.yml             # see manifest-template rule
├── flags.yml                # deterministic flag checks that fired
├── redaction-report.txt     # what was stripped and where
├── baseline/
│   ├── versions.yml
│   ├── api-config.json
│   ├── deployment.yml
│   ├── host.yml
│   ├── config/
│   ├── schemas/             # + schemas.sha256
│   ├── state/
│   └── logs/                # one file per replica
├── category/
│   └── <category-name>/
├── repro/                   # user-provided minimal repro
│   ├── steps.md
│   ├── failing.gql          # graphql-api only
│   ├── schemas/             # schema-load only
│   └── runs/                # output of infrahubctl repro commands
└── user-input/
    ├── questions-answered.md   # mirrors upstream bug-report template
    ├── screenshots/
    └── browser-har.har         # UI bugs only
```

Rules for what is and is not present:

- `README.md`, `manifest.yml`, and `flags.yml` are
  **always** at the root.
- `baseline/` is **always** populated (versions,
  api-config, deployment, host, config, schemas,
  state, logs).
- `category/<name>/` is present **only for
  categories that applied**. If only `git-sync`
  applied, only `category/git-sync/` exists; do
  not create `category/installation-startup/` or
  any other empty placeholder.
- `repro/` is present **only when the user
  provided a reproducer**. Skip it entirely
  otherwise — do not leave an empty `repro/steps.md`.
- `user-input/` **always** contains at least
  `questions-answered.md`. Sub-files
  (`screenshots/`, `browser-har.har`) appear only
  when relevant (e.g., UI bugs).

### Compliant

A git-sync-only bundle, with screenshots provided
by the user:

```text
infrahub-diagnostics-20260530-120000/
├── README.md
├── manifest.yml
├── flags.yml
├── redaction-report.txt
├── baseline/
│   ├── versions.yml
│   ├── api-config.json
│   ├── deployment.yml
│   ├── host.yml
│   ├── config/
│   ├── schemas/
│   ├── state/
│   └── logs/
├── category/
│   └── git-sync/
└── user-input/
    ├── questions-answered.md
    └── screenshots/
```

### Non-compliant

A bundle where only `git-sync` applied but the
collector created empty placeholders for the other
nine categories:

```text
infrahub-diagnostics-20260530-120000/
├── README.md
├── manifest.yml
├── ...
└── category/
    ├── installation-startup/   # empty — must not exist
    ├── git-sync/
    ├── upgrade/                # empty — must not exist
    ├── task-worker-pipeline/   # empty — must not exist
    └── ...
```

### Common mistakes

- Creating one directory per category up front "in
  case we need it later". The contract is that
  presence equals applicability — empty dirs lie
  about what was collected.
- Omitting `flags.yml` when no checks fired. The
  file must exist; an empty YAML list (`[]`) is
  the correct signal that the catalog ran and
  emitted no hits.
- Putting `redaction-report.txt` inside `baseline/`.
  It belongs at the root next to `manifest.yml` so
  the user sees it before any drill-down.

Reference: [Spec — Bundle layout](../../../dev/specs/2026-05-30-collecting-diagnostics-design.md)
