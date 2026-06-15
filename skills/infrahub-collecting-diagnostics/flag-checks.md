# Flag Checks — Deterministic Catalog

This file is the full catalog of v1 flag checks
that the skill runs in workflow step 6, after
collection and before the redaction gate. Every
check here is deterministic: it inspects a specific
collected file, applies a regex / `jq` / `yq`
selector, and emits a `flags.yml` entry on a hit.

Flag checks are **hints, never diagnoses** (see
[rules/flag-checks-deterministic.md](rules/flag-checks-deterministic.md)).
The expert who opens the bundle does the real
diagnosis. Each flag points them at the file and
excerpt that triggered it, plus any related GitHub
issues so they can correlate against known bugs.

Every entry follows the schema:

```yaml
- id: <kebab-case-id>
  severity: info | warning
  evidence:
    file: <path-relative-to-bundle-root>
    line: <optional>
    excerpt: "<one-line snippet>"
  related_issues: [<github-issue-numbers>]
  hint: "<one short sentence; never a diagnosis>"
```

Every check below reads files **already present in
the bundle** — none of them probe the running
deployment. The catalog was previously larger; flag
checks that depended on speculative probes
(`schema-hash-drift` polled the workers, the
RabbitMQ and Prefect checks needed `docker compose
exec` into the broker / Postgres) were dropped when
the skill tightened its contract to `infrahubctl`-only
for instance state.

## v1 catalog (12 checks)

### 1. `using-default-security-key`

- **Severity:** warning
- **Pattern:** read `bundle/baseline/config/compose-resolved.yml`
  (Docker Compose) or `bundle/baseline/config/helm-values.yml`
  (Kubernetes) for the value of `INFRAHUB_SECURITY_SECRET_KEY`,
  compute its sha256, and compare to the sha256 of the
  documented compose default. Compute the reference hash
  against the upstream
  [docker-compose.yml](https://github.com/opsmill/infrahub/blob/main/docker-compose.yml).
  This reads a file already on disk — the skill does
  not `docker compose exec` into the server container
  to print the env.
- **Hint:** "JWT signing key is the documented
  default — sessions issued by one server pod may
  not validate on another."
- **Related GitHub issues:**
  [#8925](https://github.com/opsmill/infrahub/issues/8925)
- **Manifest side-effect:** sets
  `infrahub.using_default_security_key: true`.

### 2. `using-default-init-token`

- **Severity:** warning
- **Pattern:** same source files as
  `using-default-security-key` — read
  `INFRAHUB_INITIAL_ADMIN_TOKEN` from the resolved
  compose config or helm values, sha256 it, compare
  to the sha256 of the documented compose default.
  Again: a file read, not an env probe inside the
  container.
- **Hint:** "Initial admin token is the documented
  default — anyone who can reach the API can
  authenticate as admin."
- **Related GitHub issues:** none specific.
- **Manifest side-effect:** sets
  `infrahub.using_default_init_token: true`.

### 3. `worker-crashloop`

- **Severity:** warning
- **Pattern (Compose):** parse
  `bundle/baseline/deployment/compose-ps.json` for
  any container whose name matches `task-worker`
  and whose `RestartCount > 3`. Cross-reference the
  container `StartedAt` to confirm restarts
  happened within the last hour.
- **Pattern (Kubernetes):** in
  `bundle/baseline/deployment/pods.json`, jq for
  any pod with `app.kubernetes.io/component=task-worker`
  whose `status.containerStatuses[].restartCount > 3`
  and `status.containerStatuses[].lastState.terminated.finishedAt`
  is within the last hour.
- **Hint:** "Task-worker container/pod has
  restarted more than 3 times in the last hour;
  read the previous-container logs first."
- **Related GitHub issues:**
  [#9036](https://github.com/opsmill/infrahub/issues/9036),
  [#9293](https://github.com/opsmill/infrahub/issues/9293),
  [#9349](https://github.com/opsmill/infrahub/issues/9349)

### 4. `branch-stuck-merging`

- **Severity:** warning
- **Pattern:** in `bundle/baseline/state/branches.txt`
  (the text output of `infrahubctl branch list`),
  any row whose status column is `MERGING`. The text
  output is the source of truth — `--json` is not
  exposed on `branch list`. If the user wants
  fresher per-branch detail, `infrahubctl branch
  report <name>` text output is collected per
  non-default branch in the `branch-merge` category.
- **Hint:** "A branch is in MERGING state; the merge
  controller may be wedged. Confirm with
  `infrahubctl branch report <name>`."
- **Related GitHub issues:** none specific (this
  pattern is the canonical symptom for several
  branch-merge bugs).

### 5. `branch-needs-rebase`

- **Severity:** warning
- **Pattern:** in `bundle/baseline/state/branches.txt`,
  any row whose status column is
  `NEED_UPGRADE_REBASE`.
- **Hint:** "Branch was open across an upgrade and
  needs `infrahubctl branch rebase <name>` before
  further changes can merge."
- **Related GitHub issues:** none specific.

### 6. `repo-error`

- **Severity:** warning
- **Pattern:** in `bundle/baseline/state/repositories.txt`
  (the text output of `infrahubctl repository list`),
  any row whose operational-status column is not
  `operational` (e.g., `degraded`, `error`,
  `unknown`).
- **Hint:** "A Git repository registered with
  Infrahub reports a non-operational status; see
  the row in repositories.txt for the failing repo."
- **Related GitHub issues:**
  [#9036](https://github.com/opsmill/infrahub/issues/9036),
  [#9349](https://github.com/opsmill/infrahub/issues/9349)

### 7. `n-1-upgrade-violation`

- **Severity:** warning
- **Pattern:** in `bundle/manifest.yml`, the
  current `infrahub.version` is more than one
  minor higher than the previous backup's recorded
  version (when the user supplies a previous
  backup) or more than one minor jump above the
  `client_version` field.
- **Hint:** "The upgrade appears to skip an
  intermediate minor version; Infrahub's documented
  upgrade policy is N to N+1."
- **Related GitHub issues:** none specific.

### 8. `oom-in-logs`

- **Severity:** warning
- **Pattern:** `grep -E 'OOMKilled|OutOfMemoryError'`
  across every file under `bundle/baseline/logs/`
  and `bundle/category/*/logs/`.
- **Hint:** "Out-of-memory event found in a
  container/pod log — the affected service was
  killed by the kernel or the JVM."
- **Related GitHub issues:** none specific.

### 9. `db-tx-memory-limit`

- **Severity:** warning
- **Pattern:**
  `grep 'Transaction memory limit reached'` in any
  log file under `bundle/baseline/logs/` or
  `bundle/category/*/logs/`. Hits typically appear
  in `infrahub-database-*.log` or
  `infrahub-server-*.log`.
- **Hint:** "Neo4j hit its per-transaction memory
  limit — a query is too large or a transaction
  isn't being batched."
- **Related GitHub issues:** none specific.

### 10. `commit-not-found`

- **Severity:** warning
- **Pattern:** `grep 'CommitNotFoundError'` in any
  `bundle/baseline/logs/*task-worker*.log` or
  `bundle/category/git-sync/logs/*.log`.
- **Hint:** "A task-worker references a Git commit
  that isn't in its local clone — multi-worker git
  race condition is the usual cause."
- **Related GitHub issues:**
  [#9036](https://github.com/opsmill/infrahub/issues/9036),
  [#9293](https://github.com/opsmill/infrahub/issues/9293)

### 11. `git-permission-denied`

- **Severity:** warning
- **Pattern:**
  `grep -E 'fatal:.*Permission denied'` in any
  `bundle/baseline/logs/*task-worker*.log` or
  `bundle/category/git-sync/logs/*.log`.
- **Hint:** "A task-worker failed a Git operation
  with Permission denied — credentials (PAT, SSH
  key) are missing, expired, or rotated."
- **Related GitHub issues:** none specific.

### 12. `host-low-resources`

- **Severity:** warning
- **Pattern:** parse `bundle/baseline/host.yml` for
  `free_memory_gb < 1` or any line under
  `disk_usage` showing < 5 GiB free
  (parse `df -h` output column 4 — `Avail`).
- **Hint:** "Host has less than 1 GiB free memory
  or less than 5 GiB free disk; Neo4j and the task
  workers degrade non-linearly under this pressure."
- **Related GitHub issues:** none specific.

## Adding a check

A new flag check is a contract: a row in this file
and a function in the workflow's step-6 runner.

The contract is intentionally narrow — the goal is
to surface known shapes that experts learn to
recognize, not to do open-ended pattern matching.
A new check must read a file that already exists in
the bundle. If you find yourself wanting to add a
check that needs a new probe — and especially one
that runs `docker compose exec`, `curl /api/...`, or
a direct DB query — stop. That probe is exactly the
kind of speculative coupling the skill removed; the
bundle does not need it.

To add a check:

1. **Add a row to this catalog** with:
   - `id` (kebab-case, prefixed with the file or
     subsystem it inspects)
   - `severity` (`info` for benign, `warning` for
     "look at this")
   - `pattern` (the exact `grep`/`jq`/`yq`
     selector against a specific collected file)
   - `hint` (one sentence; never a diagnosis)
   - `related_issues` (GitHub issue numbers if
     known)
2. **Implement the pattern in workflow step 6.**
   The implementation reads the named file from
   the bundle, applies the selector, and on a hit
   appends a `flags.yml` entry. Keep the pattern
   pure — no external network calls, no LLM
   judgement.
3. **Add an example fixture.** When a check is
   added, the corresponding eval task (in
   `eval.yaml`) seeds the bundle with a file that
   would trigger it, and the grader asserts that
   `flags.yml` contains the entry.
4. **Update related issues.** Reference URLs are
   `https://github.com/opsmill/infrahub/issues/<number>`.
   When upstream resolves an issue the check
   relates to, leave the reference — the bundle is
   archived; the historical link is what an expert
   needs.

A pattern that needs LLM judgement to evaluate is
not a flag check. Examples that should not be
added:

- "The error message looks like an auth bug" — too
  open-ended; the expert reads the logs.
- "Performance feels slow" — not deterministic; no
  fixed threshold.
- "Schema looks invalid" — that's
  `infrahubctl schema check`, which the workflow
  already runs in the `schema-load` category.

When in doubt: if you can write the selector in
five lines of `grep`/`jq`/`yq` against an existing
bundle file, it belongs here. If you can't, it
doesn't.
