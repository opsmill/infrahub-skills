# Examples — End-to-End Walk-throughs

Three realistic walk-throughs of the skill driving
a full collection cycle. Each one shows the user's
opening message, the skill's progression through
the eight workflow steps, the redaction summary,
the final bundle layout, and the hand-off summary
the expert will see first.

These are not prompts to copy — they are reference
transcripts that show the right shape and detail
level. When the skill runs for real, the commands
come from `reference.md` and the flags come from
`flag-checks.md`.

## Example 1 — Git-sync failure (Docker Compose, 2 task-worker replicas)

### User opens

> "My proposed change pipeline is failing on schema
> load — the repo isn't loading. I'm on
> docker-compose with 2 task-worker replicas. The
> error mentions `CommitNotFoundError`."

### Step 1: Capture problem

The skill notes the keywords (`docker-compose`,
`2 task-worker replicas`, `CommitNotFoundError`,
`pipeline`, `schema load`) but does not start
probing yet. The category is almost certainly
`git-sync`, and the multi-worker note matters —
this is exactly the case where per-worker
collection is non-negotiable.

### Step 2: Establish baseline

Topology detection runs in order. The first probe
succeeds:

```text
$ docker compose ps
NAME                          IMAGE                             STATUS
infrahub-cache-1              redis:7.2                         Up 4 days (healthy)
infrahub-database-1           neo4j:5.20-community              Up 4 days (healthy)
infrahub-message-queue-1      rabbitmq:3.13.7-management        Up 4 days (healthy)
infrahub-server-1             registry.opsmill.io/...:1.9.6     Up 4 days (healthy)
infrahub-task-manager-1       prefecthq/prefect:3-latest        Up 4 days (healthy)
infrahub-task-manager-db-1    postgres:16                       Up 4 days (healthy)
infrahub-task-worker-1        registry.opsmill.io/...:1.9.6     Up 4 days (healthy)
infrahub-task-worker-2        registry.opsmill.io/...:1.9.6     Up 4 days (healthy)
```

Confirmed: Docker Compose, two `task-worker`
replicas, server version `1.9.6` from the tags.

The skill creates the bundle directory:

```text
infrahub-diagnostics-20260530-141200/
```

Then runs the Docker Compose baseline block from
[reference.md § 2.1](reference.md#21-docker-compose):

```text
bundle/baseline/
├── api-config.json            # /api/config → version=1.9.6 edition=community
├── deployment/
│   ├── compose-images.txt
│   ├── compose-ps.json
│   └── docker-networks.txt
├── config/
│   ├── .infrahub.yml
│   └── compose-resolved.yml
├── host.yml                   # cpu_cores=8 memory_gb=16
├── logs/
│   ├── infrahub-cache-1.log
│   ├── infrahub-database-1.log
│   ├── infrahub-message-queue-1.log
│   ├── infrahub-server-1.log
│   ├── infrahub-task-manager-1.log
│   ├── infrahub-task-manager-db-1.log
│   ├── infrahub-task-worker-1.log
│   └── infrahub-task-worker-2.log
├── schemas-repo/              # the user's schemas/ directory verbatim
├── schemas-repo.sha256
├── state/
│   ├── branches.json
│   ├── recent-tasks.json
│   ├── repositories.txt
│   ├── schema-kinds.txt
│   └── telemetry.json
└── versions/
    ├── docker-compose.txt
    ├── docker.txt
    ├── infrahubctl-info.txt
    ├── infrahubctl.txt
    ├── python3.txt
    └── uname.txt
```

### Step 3: Classify (user-gate)

The skill works through the bug-report fields:

```text
Skill: "Infrahub version on the server?"
User:  "1.9.6"   (cross-checked against api-config.json — match)

Skill: "Edition?"
User:  "community"

Skill: "Deployment type?"
User:  "Docker Compose"

Skill: "Which component is affected?"
User:  "Git Integration"

Skill: "Current behavior — what you observe?"
User:  "Pipeline fails, schemas not loaded"

Skill: "Expected behavior?"
User:  "Pipeline completes; schemas loaded from repo"

Skill: "Steps to reproduce?"
User:  "Push to main; wait for the pipeline"

Skill: "Error message verbatim?"
User:  "CommitNotFoundError: Commit abc123def not found"

Skill: "When did it start?"
User:  "Yesterday"

Skill: "Reproducible?"
User:  "Every time"

Skill: "What changed recently?"
User:  "We added a new task-worker replica"

Skill: "Impact?"
User:  "Blocker — no PCs can complete"
```

Based on the error, the new-replica change, and the
"Git Integration" component, the skill proposes:

```text
Skill: "Classifying as `git-sync`. Proceed?"
User:  "Yes"
```

### Step 4: Targeted collection

The skill runs the `git-sync` block from
[reference.md § 3.3](reference.md#33-git-sync).
Critically, both workers are inspected — not just
the first:

```text
bundle/category/git-sync/
├── config/
│   └── .infrahub.yml
├── repos-graphql.json
├── repositories.txt
└── workers/
    ├── infrahub-task-worker-1/
    │   ├── git-dir-listing.txt
    │   ├── recent.log
    │   └── repo-status.txt
    └── infrahub-task-worker-2/
        ├── git-dir-listing.txt
        ├── recent.log
        └── repo-status.txt
```

`workers/infrahub-task-worker-1/repo-status.txt`
shows:

```text
===== /opt/infrahub/git/network-schemas/ =====
## main...origin/main
nothing to commit, working tree clean
--- recent commits ---
abc123d Schema bump for VLAN groups
def4567 Initial schema commit
--- remote ---
origin  https://github.com/example/network-schemas.git (fetch)
```

`workers/infrahub-task-worker-2/repo-status.txt`
shows the smoking gun:

```text
===== /opt/infrahub/git/network-schemas/ =====
fatal: not a git repository (or any of the parent directories): .git
```

Worker 2 was never seeded with the repo clone. This
is the pattern in
[#9036](https://github.com/opsmill/infrahub/issues/9036).

### Step 5: Run flag checks

Two checks fire (see
[flag-checks.md](flag-checks.md) for the catalog):

```yaml
# bundle/flags.yml
- id: commit-not-found
  severity: warning
  evidence:
    file: baseline/logs/infrahub-task-worker-2.log
    line: 4521
    excerpt: "CommitNotFoundError: Commit abc123def not found"
  related_issues: [9036, 9293]
  hint: "Worker reports a commit that should exist but doesn't —
         expert should check whether this worker's /opt/infrahub/git
         is in sync with the others."

- id: repo-error
  severity: warning
  evidence:
    file: category/git-sync/repos-graphql.json
    excerpt: "operational_status: degraded"
  related_issues: [9349]
  hint: "CoreGenericRepository reports a non-operational status;
         see the repo-graphql output for the failing repo name."
```

### Step 6: Redact + summary (user-gate)

Tier-1 sweeps the bundle. The redaction report
shows:

```text
redaction-report.txt summary:
  files_touched: 12
  replacements:  38

  env-key matches:        14   (INFRAHUB_*_PASSWORD, INFRAHUB_API_TOKEN)
  url credentials:         3   (PAT-style tokens in repo URLs)
  jwt shapes:              0
  aws keys:                0
  private-key blocks:      0
  init-token uuids:        2
```

Example of a URL-credential replacement in the
`.infrahub.yml` copy:

```diff
-  location: https://ghp_AbCdEf1234567890@github.com/example/network-schemas.git
+  location: https://***REDACTED***@github.com/example/network-schemas.git
```

Tier-2 summary prints to the user:

```text
Sample distinct IPs:
  RFC1918: 10.0.42.7, 10.0.42.12, 172.18.0.2 ... (8 total)
  Public:  (none)
Sample distinct hostnames:
  github.com, example.internal, registry.opsmill.io ... (5 total)
Sample distinct customer-looking strings:
  network-schemas (1 total)
Webhook URLs found: (none)

For each group, choose: keep | redact-all | case-by-case
```

The user picks: `RFC1918=keep`, `hostnames=keep`,
`customer_strings=keep` (the schema repo name isn't
sensitive). No webhook URLs to triage.

### Step 7: Finalize

`bundle/manifest.yml` is written. The
`problem.category` is `git-sync`,
`collected.multi_replica_coverage: true`,
`infrahub.using_default_security_key: false`.

`bundle/README.md` is written with a five-line
expert summary and a pointer to `manifest.yml`.

The skill prints:

```text
Bundle written to:
  /home/user/proj/infrahub-diagnostics-20260530-141200/

To package for hand-off:
  tar czf infrahub-diagnostics-20260530-141200.tgz \
          infrahub-diagnostics-20260530-141200/
```

### Step 8: Hand-off (user-gate)

```text
Expert-ready summary:
- Infrahub 1.9.6 community, docker-compose, 2 task-worker replicas.
- Problem: git-sync — schemas not loading; CommitNotFoundError on PC pipeline.
- Started yesterday after adding a second task-worker replica.
- Flags fired: commit-not-found, repo-error.
- task-worker-2 has no /opt/infrahub/git/network-schemas clone; -1 does.
  Multi-worker git race; see #9036, #9293.

Hand to OpsMill support via your usual channel.

If you also want to file a public GitHub issue, switch to the
`infrahub-reporting-issues` skill — it routes by component and
pre-fills only the fields that template requires.
```

## Example 2 — Upgrade with stuck branch (Kubernetes/Helm)

### User opens

> "After `helm upgrade` from 1.8 to 1.9, my branch
> `feature/new-vlans` is stuck at
> `NEED_UPGRADE_REBASE` and I can't merge it."

### Step 2: Establish baseline

Detection probes `docker compose ps` (no socket),
falls through to:

```text
$ kubectl -n infrahub get pods
NAME                                       READY   STATUS    RESTARTS   AGE
infrahub-cache-0                           1/1     Running   0          2h
infrahub-database-0                        1/1     Running   0          2h
infrahub-message-queue-0                   1/1     Running   0          2h
infrahub-server-7d68f4c5b-2zwxq            1/1     Running   0          2h
infrahub-server-7d68f4c5b-h4lvg            1/1     Running   0          2h
infrahub-task-manager-0                    1/1     Running   0          2h
infrahub-task-manager-db-0                 1/1     Running   0          2h
infrahub-task-worker-6f9c8b7d-jqz4r        1/1     Running   3          2h
infrahub-task-worker-6f9c8b7d-x7vmn        1/1     Running   1          2h
```

Kubernetes is confirmed. The skill runs the K8s
baseline from
[reference.md § 2.2](reference.md#22-kubernetes).
`api-config.json` reports version `1.9.0`,
edition `enterprise`.

`bundle/baseline/state/branches.json` shows:

```json
[
  {"name": "main", "status": "OPEN", "is_default": true},
  {"name": "feature/new-vlans",
   "status": "NEED_UPGRADE_REBASE",
   "updated_at": "2026-05-30T11:42:08Z"}
]
```

### Step 3: Classify (user-gate)

Bug-report-template walk-through. The user reports
the upgrade was from 1.8 to 1.9 (one minor — within
the N-1 rule). Component: `API Server`. Category
proposal: `upgrade`. Confirmed.

### Step 4: Targeted collection

The K8s `upgrade` block runs (see
[reference.md § 3.2](reference.md#32-upgrade)):

```text
bundle/category/upgrade/
├── branches/
│   └── list.json
├── compose-images.txt        # k8s variant: pod image list from kubectl
├── helm-history.txt
├── logs/
│   ├── infrahub-server-7d68f4c5b-2zwxq.log
│   ├── infrahub-server-7d68f4c5b-h4lvg.log
│   ├── infrahub-task-worker-6f9c8b7d-jqz4r.log
│   └── infrahub-task-worker-6f9c8b7d-x7vmn.log
├── neo4j-report/
│   ├── run.log
│   └── tmp/                  # the neo4j-admin report tgz contents
└── pods-yaml.txt
```

`helm-history.txt`:

```text
REVISION  UPDATED                   STATUS    CHART          APP VERSION  DESCRIPTION
1         2026-04-15 09:12:08 UTC   deployed  infrahub-2.4   1.8.5        Install complete
2         2026-05-30 12:14:22 UTC   deployed  infrahub-2.5   1.9.0        Upgrade complete
```

### Step 5: Run flag checks

```yaml
# bundle/flags.yml
- id: branch-needs-rebase
  severity: warning
  evidence:
    file: baseline/state/branches.json
    excerpt: '{"name": "feature/new-vlans", "status": "NEED_UPGRADE_REBASE"}'
  related_issues: []
  hint: "Branch was open across an upgrade boundary and needs to be
         rebased before further changes can be merged. The user runs
         `infrahubctl branch rebase feature/new-vlans` to clear this."

- id: worker-crashloop
  severity: warning
  evidence:
    file: baseline/deployment/pods.json
    excerpt: '"name":"infrahub-task-worker-6f9c8b7d-jqz4r","restartCount":3'
  related_issues: []
  hint: "task-worker pod has restarted 3 times since the upgrade — check
         the previous-container logs at logs/<pod>.previous.log."
```

No `n-1-upgrade-violation` — 1.8 to 1.9 is within
range.

### Step 6: Redact + summary (user-gate)

Tier-1 sweeps. `helm-values.yml` is redacted
aggressively because Helm values include the
container registry secret and the Postgres
password:

```diff
-imagePullSecrets:
-  - name: ghcr-creds
-imageRegistryToken: "ghp_AbCdEf..."
+imagePullSecrets:
+  - name: ghcr-creds
+imageRegistryToken: "***REDACTED:env-key***"
```

Tier-2 summary flags an enterprise customer name in
the `CoreAccount` listing. User picks
`customer_strings=redact-all` (the bundle is going
to OpsMill, but their corporate policy strips
identifying strings).

### Step 7: Finalize

`manifest.yml.problem.category: "upgrade"`,
`collected.multi_replica_coverage: true`,
`infrahub.edition: "enterprise"`.

### Step 8: Hand-off

```text
Expert-ready summary:
- Infrahub 1.9.0 enterprise, kubernetes (Helm), 2 server + 2 task-worker pods.
- Problem: upgrade — branch feature/new-vlans stuck NEED_UPGRADE_REBASE.
- Upgrade from 1.8.5 to 1.9.0 about 2 hours ago (helm history confirms).
- Flags fired: branch-needs-rebase, worker-crashloop.
- One task-worker pod restarted 3x since upgrade; see *.previous.log.

Hand to OpsMill support via your usual channel.
```

## Example 3 — Performance investigation (Docker Compose)

### User opens

> "The UI is unusably slow when I open the device
> list. It used to be quick. Nothing changed on my
> end."

### Step 1-3: Capture, baseline, classify

The skill walks the same first three steps. The
user reports:

- Version: `1.9.6` community
- Topology: Docker Compose (single replica each)
- Component: `Frontend UI` — but the underlying
  cause is server-side
- Current: device list page hangs > 30s
- Expected: < 2s
- Started: "got worse over the last week"
- Reproducible: every time
- Impact: major

The skill proposes `performance` (UI slowness with
no client-side changes points at the data plane).
Confirmed.

### Step 4: Targeted collection

Block from
[reference.md § 3.8](reference.md#38-performance):

```text
bundle/category/performance/
├── host/
│   └── resources.txt
├── neo4j/
│   └── active-queries.txt
├── stats/
│   └── docker-stats.txt
└── telemetry.json
```

`stats/docker-stats.txt`:

```text
CONTAINER ID   NAME                    CPU %    MEM USAGE / LIMIT     MEM %
b3a4...        infrahub-database-1     145.3%   12.8GiB / 14GiB       91.4%
1c2d...        infrahub-server-1       65.2%    1.1GiB / 2GiB         55.0%
8f9e...        infrahub-task-worker-1  3.1%     420MiB / 2GiB         20.5%
...
```

`neo4j/active-queries.txt` shows three queries each
running > 8000ms — long-running device-list query
with no LIMIT.

`host/resources.txt`:

```text
--- nproc ---
4
--- free -h ---
              total        used        free      shared  buff/cache   available
Mem:           15Gi        14Gi       380Mi        24Mi       690Mi       0.7Gi
--- df -h ---
/dev/sda1       100G    93G    7.0G  94% /
```

### Step 5: Run flag checks

```yaml
# bundle/flags.yml
- id: host-low-resources
  severity: warning
  evidence:
    file: category/performance/host/resources.txt
    excerpt: "Mem available: 0.7Gi; /dev/sda1 93G/100G (94% used)"
  related_issues: []
  hint: "Free memory under 1 GiB and disk under 7 GiB free. Neo4j
         hot-path queries spill to disk under memory pressure;
         expert should size up the host or cap neo4j heap."
```

The database is at 91% memory and the host is at
94% disk. The skill does not claim that's the root
cause — but the `host-low-resources` flag points
the expert at it.

### Step 6: Redact + summary (user-gate)

The bundle contains real device names in the Neo4j
query text and the telemetry payload. The user
picks `customer_strings=redact-all` — these are
production device hostnames they don't want
travelling.

Tier-1 already masked the database password from
`compose-resolved.yml`; the Tier-2 replacement
sweeps the device names:

```diff
-Query: MATCH (n:Device) WHERE n.name = 'prod-edge-rtr-42' ...
+Query: MATCH (n:Device) WHERE n.name = '***REDACTED:device***' ...
```

### Step 7-8: Finalize + hand-off

```text
Expert-ready summary:
- Infrahub 1.9.6 community, docker-compose, single replica.
- Problem: performance — device list UI hangs > 30s.
- Got worse over the last week; no recent code/schema changes.
- Flags fired: host-low-resources.
- Host: 4 cores, 15 Gi RAM (0.7 Gi free), 100 G disk (94% used).
- Neo4j top active query is a device-list scan taking ~8s with no LIMIT.

Hand to OpsMill support via your usual channel.
```

## Notes on the bundle layouts

In all three examples, the bundle ends with the
same top-level shape:

```text
infrahub-diagnostics-YYYYMMDD-HHMMSS/
├── README.md
├── manifest.yml
├── flags.yml
├── redaction-report.txt
├── baseline/
├── category/<one or more>/
├── repro/                       # optional, populated only when user provided
└── user-input/
```

Differences between examples:

- **Git-sync** had no `repro/` subtree — the issue
  was on-host, not in user-provided code.
- **Upgrade** had a `neo4j-report/` subtree under
  `category/upgrade/` with the bundled
  `neo4j-admin` health report.
- **Performance** had no `user-input/` (no
  screenshots, no HAR) — the user opted not to add
  any.

What's invariant: every example carries every
multi-replica service's logs as separate files,
the manifest mirrors the bug-report template, and
the redaction report records what was masked.
