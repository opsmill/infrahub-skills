# Flag Checks — Deterministic Catalog

This file is the full catalog of v1 flag checks
that the skill runs in workflow step 5, after
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

## v1 catalog (15 checks)

### 1. `using-default-security-key`

- **Severity:** warning
- **Pattern:** sha256 of `INFRAHUB_SECURITY_SECRET_KEY`
  (read from `bundle/baseline/config/compose-resolved.yml`
  or `bundle/baseline/config/helm-values.yml`)
  matches the documented compose default. Compute
  against the upstream
  [docker-compose.yml](https://github.com/opsmill/infrahub/blob/main/docker-compose.yml).
- **Hint:** "JWT signing key is the documented
  default — sessions issued by one server pod may
  not validate on another."
- **Related GitHub issues:**
  [#8925](https://github.com/opsmill/infrahub/issues/8925)
- **Manifest side-effect:** sets
  `infrahub.using_default_security_key: true`.

### 2. `using-default-init-token`

- **Severity:** warning
- **Pattern:** sha256 of
  `INFRAHUB_INITIAL_ADMIN_TOKEN` (same source files
  as above) matches the documented compose default.
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
- **Pattern:** in `bundle/baseline/state/branches.json`,
  any element with `status: "MERGING"` and
  `updated_at` older than 10 minutes (measured
  against `manifest.generated_at`).
- **Hint:** "A branch has been in MERGING state
  for more than 10 minutes; the merge controller
  is likely wedged."
- **Related GitHub issues:** none specific (this
  pattern is the canonical symptom for several
  branch-merge bugs).

### 5. `branch-needs-rebase`

- **Severity:** warning
- **Pattern:** in `bundle/baseline/state/branches.json`,
  any element with `status: "NEED_UPGRADE_REBASE"`.
- **Hint:** "Branch was open across an upgrade and
  needs `infrahubctl branch rebase <name>` before
  further changes can merge."
- **Related GitHub issues:** none specific.

### 6. `repo-error`

- **Severity:** warning
- **Pattern:** in
  `bundle/category/git-sync/repos-graphql.json`,
  any `CoreGenericRepository` whose
  `operational_status != "operational"`.
- **Hint:** "A Git repository registered with
  Infrahub reports a non-operational status; see
  the `name` and `commit` fields for the failing
  repo."
- **Related GitHub issues:**
  [#9036](https://github.com/opsmill/infrahub/issues/9036),
  [#9349](https://github.com/opsmill/infrahub/issues/9349)

### 7. `schema-hash-drift`

- **Severity:** warning
- **Pattern:** the `/api/schema/summary` `hash`
  field collected from each worker (when
  multi-replica probing is possible) does not
  match across workers. With a single-replica
  deployment this check is skipped.
- **Hint:** "Workers report different schema
  hashes — one worker is on an older schema than
  another. The schema-load propagation step
  didn't reach every worker."
- **Related GitHub issues:** none specific.

### 8. `n-1-upgrade-violation`

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

### 9. `rabbit-queue-backlog`

- **Severity:** warning
- **Pattern:** parse
  `bundle/category/task-worker-pipeline/rabbitmq/queues.txt`
  for any queue whose `messages` column exceeds
  100.
- **Hint:** "RabbitMQ queue depth is over 100;
  consumers may not be keeping up or are wedged."
- **Related GitHub issues:** none specific.

### 10. `prefect-many-failed-runs`

- **Severity:** warning
- **Pattern:** parse
  `bundle/category/task-worker-pipeline/prefect/recent-runs.txt`
  for more than 5 rows with `state_type = 'FAILED'`
  whose `start_time` is within the last hour.
- **Hint:** "More than 5 Prefect flow runs failed
  in the last hour — likely a systemic issue
  rather than an isolated task failure."
- **Related GitHub issues:** none specific.

### 11. `oom-in-logs`

- **Severity:** warning
- **Pattern:** `grep -E 'OOMKilled|OutOfMemoryError'`
  across every file under `bundle/baseline/logs/`
  and `bundle/category/*/logs/`.
- **Hint:** "Out-of-memory event found in a
  container/pod log — the affected service was
  killed by the kernel or the JVM."
- **Related GitHub issues:** none specific.

### 12. `db-tx-memory-limit`

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

### 13. `commit-not-found`

- **Severity:** warning
- **Pattern:** `grep 'CommitNotFoundError'` in any
  `bundle/baseline/logs/*task-worker*.log` or
  `bundle/category/git-sync/workers/*/recent.log`.
- **Hint:** "A task-worker references a Git commit
  that isn't in its local clone — multi-worker git
  race condition is the usual cause."
- **Related GitHub issues:**
  [#9036](https://github.com/opsmill/infrahub/issues/9036),
  [#9293](https://github.com/opsmill/infrahub/issues/9293)

### 14. `git-permission-denied`

- **Severity:** warning
- **Pattern:**
  `grep -E 'fatal:.*Permission denied'` in any
  `bundle/baseline/logs/*task-worker*.log` or
  `bundle/category/git-sync/workers/*/recent.log`.
- **Hint:** "A task-worker failed a Git operation
  with Permission denied — credentials (PAT, SSH
  key) are missing, expired, or rotated."
- **Related GitHub issues:** none specific.

### 15. `host-low-resources`

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
and a function in the workflow's step-5 runner.

The contract is intentionally narrow — the goal is
to surface known shapes that experts learn to
recognize, not to do open-ended pattern matching.

To add one:

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
2. **Implement the pattern in workflow step 5.**
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
five lines of `grep`/`jq`/`yq`, it belongs here.
If you can't, it doesn't.
