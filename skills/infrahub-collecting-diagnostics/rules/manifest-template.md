---
title: manifest.yml field contract
impact: HIGH
tags: manifest, bug-report-template, version-cross-check
---

## manifest.yml field contract

Impact: HIGH

`manifest.yml` is the bundle's table of contents.
Experts read it before any other file. It mirrors
the upstream bug-report issue template so the
`problem` block is transcribable straight into a
public issue without rework when the user is later
ready to file one.

### Why it matters

A bundle with a malformed or partial manifest forces
the expert to crawl the directory tree to figure out
what is present and what was actually observed.
Worse, a missing `problem.category` means the expert
has to guess which `category/` subtree to read first.
Strict adherence to the schema is the contract that
makes triage fast.

### What to do

Write `manifest.yml` with all required top-level
keys. The schema:

```yaml
bundle_version: "1.0"
generated_at: "2026-05-30T12:00:00Z"
skill_version: "1.2.5"               # plugin version
infrahub:
  version: "1.9.6"                   # from /api/config
  edition: "community"               # community | enterprise
  using_default_security_key: false  # hash compare, not value
  using_default_init_token: false
deployment:
  topology: "docker-compose"         # docker-compose|kubernetes|local-dev|manual
  worker_replicas: 2
  image_shas:
    infrahub-server: "sha256:..."
    task-worker: "sha256:..."
host:
  os: "Linux 6.x"
  cpu_cores: 8
  memory_gb: 16
problem:
  # Mirrors opsmill/infrahub bug-report template
  component: "Git Integration"
  current_behavior: "..."
  expected_behavior: "..."
  steps_to_reproduce: "..."
  error_message: "..."
  first_observed: "2026-05-29"
  reproducible: true
  impact: "blocker"
  category: "git-sync"
collected:
  baseline: true
  category_dirs: ["git-sync"]
  repro_included: true
  multi_replica_coverage: true
redaction:
  applied: true
  rules_version: "1.0"
  files_touched: 47
  replacements: 192
  user_review_completed: true
  user_choices:
    public_ips: "redact-all"
    hostnames: "keep"
    customer_strings: "redact-all"
```

Every top-level key (`bundle_version`,
`generated_at`, `skill_version`, `infrahub`,
`deployment`, `host`, `problem`, `collected`,
`redaction`) is required.

**Version cross-check.** The Infrahub version
reported by `infrahubctl version` (client) and the
server's `/api/config` endpoint can diverge — for
example after a partial upgrade. When they
disagree, record both:

```yaml
infrahub:
  version: "1.9.6"                # server (/api/config)
  client_version: "1.8.2"         # infrahubctl version
  version_mismatch: true
```

…and emit a flag entry in `flags.yml` so the
expert sees the divergence immediately.

### Compliant

A complete manifest for a git-sync investigation:

```yaml
bundle_version: "1.0"
generated_at: "2026-05-30T12:00:00Z"
skill_version: "1.2.5"
infrahub:
  version: "1.9.6"
  edition: "community"
  using_default_security_key: false
  using_default_init_token: false
deployment:
  topology: "docker-compose"
  worker_replicas: 2
host:
  os: "Linux 6.x"
  cpu_cores: 8
  memory_gb: 16
problem:
  component: "Git Integration"
  current_behavior: "Proposed change pipeline fails on schema load"
  expected_behavior: "Pipeline completes; schemas loaded from repo"
  steps_to_reproduce: "Push to main; wait for pipeline"
  error_message: "CommitNotFoundError: Commit abc123 not found"
  first_observed: "2026-05-29"
  reproducible: true
  impact: "blocker"
  category: "git-sync"
collected:
  baseline: true
  category_dirs: ["git-sync"]
  repro_included: false
  multi_replica_coverage: true
redaction:
  applied: true
  rules_version: "1.0"
  files_touched: 12
  replacements: 38
  user_review_completed: true
  user_choices:
    public_ips: "redact-all"
    hostnames: "keep"
```

### Non-compliant

Missing `problem.category` — the expert cannot
locate the relevant `category/` subtree:

```yaml
bundle_version: "1.0"
generated_at: "2026-05-30T12:00:00Z"
infrahub:
  version: "1.9.6"
problem:
  component: "Git Integration"
  current_behavior: "..."
  # category missing
```

### Common mistakes

- Omitting `problem.category` because the user
  picked "everything" mode. In that case set
  `problem.category: "unknown"` and list every
  populated subtree in `collected.category_dirs`.
- Recording only one of `infrahubctl version` /
  `/api/config` when they disagree. Both must
  appear, plus `version_mismatch: true`, plus a
  matching `flags.yml` entry.
- Writing the literal `INFRAHUB_SECURITY_SECRET_KEY`
  value instead of the `using_default_security_key`
  boolean. The boolean is the diagnostic signal;
  the value is sensitive.

Reference: [opsmill/infrahub bug_report.yml](https://github.com/opsmill/infrahub/blob/main/.github/ISSUE_TEMPLATE/bug_report.yml)
