# Examples — End-to-End Walk-throughs

Three realistic walk-throughs of the skill driving
a full collection cycle. Each one shows the user's
opening message, the skill's progression through
the nine workflow steps (four user-gates), the
redaction summary, the final bundle layout, and the
hand-off summary the expert will see first.

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

### Step 2: Capture connection info (user-gate)

The skill asks before any probe:

```text
Skill:  Before I start, I need two things:

        1. The URL or IP infrahubctl should use to reach Infrahub.
           E.g., http://localhost:8000 or https://infrahub.example.com.

        2. An API token. Your API token is only used locally by
           infrahubctl to query state on your behalf. It is never
           written to the bundle. The skill's redactor masks the
           token before any bundle file is finalized. The token is
           not sent anywhere outside your machine.

User:   URL is http://localhost:8000. Token: ift_2f7c...d91a

Skill:  Thanks — adding the token to the redactor mask list now,
        exporting INFRAHUB_ADDRESS and INFRAHUBCTL_TOKEN, and
        continuing.
```

### Step 3: Establish baseline

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
├── deployment/
│   ├── compose-images.txt
│   ├── compose-ps.json
│   ├── compose-top.txt
│   ├── docker-networks.txt
│   ├── inspect-infrahub-server-1.json
│   ├── inspect-infrahub-task-worker-1.json
│   └── inspect-infrahub-task-worker-2.json
├── config/
│   ├── .infrahub.yml
│   ├── compose-resolved.yml
│   └── docker-compose.yml
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
│   ├── branches.txt
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

### Step 4: Classify (user-gate)

The skill works through the bug-report fields:

```text
Skill: "Infrahub version on the server?"
User:  "1.9.6"   (cross-checked against infrahubctl version — match)

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

### Step 5: Targeted collection

The skill runs the `git-sync` block from
[reference.md § 3.3](reference.md#33-git-sync).
Both workers' logs are pulled — multi-worker race
conditions are exactly what the per-replica
collection is for:

```text
bundle/category/git-sync/
├── config/
│   └── .infrahub.yml
├── logs/
│   ├── infrahub-task-worker-1.log
│   └── infrahub-task-worker-2.log
└── repositories.txt
```

`logs/infrahub-task-worker-2.log` shows the smoking
gun (a few lines in):

```text
2026-05-30 13:42:09 ERROR  infrahub.tasks.git_sync: CommitNotFoundError
  Commit abc123def not found in /opt/infrahub/git/network-schemas
Traceback (most recent call last):
  ...
infrahub.exceptions.CommitNotFoundError: Commit abc123def not found
```

`logs/infrahub-task-worker-1.log` does not contain
that error — only worker-2 sees it. This is the
multi-worker race-condition pattern in
[#9036](https://github.com/opsmill/infrahub/issues/9036),
where one worker was never seeded with a fresh
clone after the new replica was scaled up.

`repositories.txt` (from `infrahubctl repository
list`) shows the affected repo with an operational
status of `degraded`.

### Step 6: Run flag checks

Two checks fire (see
[flag-checks.md](flag-checks.md) for the catalog):

```yaml
# bundle/flags.yml
- id: commit-not-found
  severity: warning
  evidence:
    file: category/git-sync/logs/infrahub-task-worker-2.log
    line: 12
    excerpt: "CommitNotFoundError: Commit abc123def not found"
  related_issues: [9036, 9293]
  hint: "Worker reports a commit that should exist but doesn't —
         multi-worker git race is the usual cause."

- id: repo-error
  severity: warning
  evidence:
    file: baseline/state/repositories.txt
    excerpt: "network-schemas  degraded"
  related_issues: [9349]
  hint: "A Git repository registered with Infrahub reports a
         non-operational status; see repositories.txt for the row."
```

### Step 7: Redact + summary (user-gate)

Tier-1 sweeps the bundle. The redaction report
shows:

```text
redaction-report.txt summary:
  files_touched: 12
  replacements:  39

  env-key matches:        14   (INFRAHUB_*_PASSWORD, INFRAHUB_API_TOKEN)
  url credentials:         3   (PAT-style tokens in repo URLs)
  jwt shapes:              0
  aws keys:                0
  private-key blocks:      0
  init-token uuids:        2
  user-provided token:     1   (INFRAHUBCTL_TOKEN; masked everywhere)
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

### Step 8: Finalize

`bundle/manifest.yml` is written. The
`problem.category` is `git-sync`,
`collected.multi_replica_coverage: true`,
`collected.infrahubctl_state: true`,
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

### Step 9: Hand-off (user-gate)

```text
Expert-ready summary:
- Infrahub 1.9.6 community, docker-compose, 2 task-worker replicas.
- Problem: git-sync — schemas not loading; CommitNotFoundError on PC pipeline.
- Started yesterday after adding a second task-worker replica.
- Flags fired: commit-not-found, repo-error.
- task-worker-2's logs show the CommitNotFoundError; task-worker-1's
  don't. Multi-worker git race; see #9036, #9293.

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

### Step 2: Capture connection info (user-gate)

```text
Skill:  Two questions before I start:

        1. The URL or IP for Infrahub — for a Kubernetes deployment
           that's usually the ingress host or a port-forward target.
        2. An API token. Your API token is only used locally by
           infrahubctl to query state on your behalf. It is never
           written to the bundle. The skill's redactor masks the
           token before any bundle file is finalized. The token is
           not sent anywhere outside your machine.

User:   https://infrahub.acme.internal — token is ift_a91...22fe

Skill:  Got it. Adding the token to the redactor mask list,
        exporting INFRAHUB_ADDRESS and INFRAHUBCTL_TOKEN.
```

### Step 3: Establish baseline

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
`infrahubctl info --detail` reports version
`1.9.0`, edition `enterprise`.

`bundle/baseline/state/branches.txt` (text output of
`infrahubctl branch list`) shows:

```text
NAME                STATUS                IS_DEFAULT  ORIGIN
main                OPEN                  true        -
feature/new-vlans   NEED_UPGRADE_REBASE   false       main
```

### Step 4: Classify (user-gate)

Bug-report-template walk-through. The user reports
the upgrade was from 1.8 to 1.9 (one minor — within
the N-1 rule). Component: `API Server`. Category
proposal: `upgrade`. Confirmed.

### Step 5: Targeted collection

The K8s `upgrade` block runs (see
[reference.md § 3.2](reference.md#32-upgrade)):

```text
bundle/category/upgrade/
├── branches/
│   └── list.txt
├── compose-images.txt        # k8s variant: pod image list from kubectl
├── helm-history.txt
├── logs/
│   ├── infrahub-database-0-database.log
│   ├── infrahub-database-0.log
│   ├── infrahub-server-7d68f4c5b-2zwxq.log
│   ├── infrahub-server-7d68f4c5b-h4lvg.log
│   ├── infrahub-task-worker-6f9c8b7d-jqz4r.log
│   └── infrahub-task-worker-6f9c8b7d-x7vmn.log
└── pods-yaml.txt
```

`helm-history.txt`:

```text
REVISION  UPDATED                   STATUS    CHART          APP VERSION  DESCRIPTION
1         2026-04-15 09:12:08 UTC   deployed  infrahub-2.4   1.8.5        Install complete
2         2026-05-30 12:14:22 UTC   deployed  infrahub-2.5   1.9.0        Upgrade complete
```

The database-pod logs (`infrahub-database-0.log`)
are where Neo4j prints any migration-time errors —
the skill no longer runs `neo4j-admin server
report`, so the container's own log is the source.

### Step 6: Run flag checks

```yaml
# bundle/flags.yml
- id: branch-needs-rebase
  severity: warning
  evidence:
    file: baseline/state/branches.txt
    excerpt: "feature/new-vlans   NEED_UPGRADE_REBASE   false   main"
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

### Step 7: Redact + summary (user-gate)

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
the user-provided notes. User picks
`customer_strings=redact-all` (the bundle is going
to OpsMill, but their corporate policy strips
identifying strings).

### Step 8: Finalize

`manifest.yml.problem.category: "upgrade"`,
`collected.multi_replica_coverage: true`,
`collected.infrahubctl_state: true`,
`infrahub.edition: "enterprise"`.

### Step 9: Hand-off

```text
Expert-ready summary:
- Infrahub 1.9.0 enterprise, kubernetes (Helm), 2 server + 2 task-worker pods.
- Problem: upgrade — branch feature/new-vlans stuck NEED_UPGRADE_REBASE.
- Upgrade from 1.8.5 to 1.9.0 about 2 hours ago (helm history confirms).
- Flags fired: branch-needs-rebase, worker-crashloop.
- One task-worker pod restarted 3x since upgrade; see *.previous.log.
- Database-pod logs in category/upgrade/logs/infrahub-database-0.log
  cover the upgrade-time interval — start there for migration errors.

Hand to OpsMill support via your usual channel.
```

## Example 3 — Performance investigation (Docker Compose), user declines token

### User opens

> "The UI is unusably slow when I open the device
> list. It used to be quick. Nothing changed on my
> end."

### Step 1: Capture problem

Notes the symptom (slow UI, device list), the
"nothing changed" claim (typical), the implicit
local deployment (no helm mention).

### Step 2: Capture connection info (user-gate) — token declined

```text
Skill:  Two questions before I start:

        1. The URL or IP for Infrahub. E.g., http://localhost:8000.
        2. An API token. Your API token is only used locally by
           infrahubctl to query state on your behalf. It is never
           written to the bundle. The skill's redactor masks the
           token before any bundle file is finalized. The token is
           not sent anywhere outside your machine.

User:   URL is http://localhost:8000. I'd rather not share a token
        with an AI tool.

Skill:  Understood. I'll collect topology, container logs, host
        fingerprint, and read your local config files, and skip
        everything that needs infrahubctl against the instance.
        The bundle will be partial — I'll note it in README.md and
        in manifest.yml (collected.infrahubctl_state: false). That's
        still useful: docker stats and the database/server logs
        carry most of what an expert needs for a performance issue.
```

### Step 3: Establish baseline

The user reports:

- Version: `1.9.6` community (the user supplied it
  verbally; the skill cannot cross-check via
  `infrahubctl info` without a token)
- Topology: Docker Compose (single replica each)
- Component: `Frontend UI` — but the underlying
  cause is server-side
- Started: "got worse over the last week"

Baseline runs in the no-token mode: every block
that needs `infrahubctl` is skipped; everything
else (deployment, logs, host, file reads) runs as
usual.

### Step 4: Classify (user-gate)

The skill proposes `performance` (UI slowness with
no client-side changes points at the data plane).
Confirmed.

### Step 5: Targeted collection

Block from
[reference.md § 3.8](reference.md#38-performance):

```text
bundle/category/performance/
├── host/
│   └── resources.txt
└── stats/
    └── docker-stats.txt
```

`telemetry.json` is **skipped** — that's an
`infrahubctl` call. The expert will read
`docker stats` + the database container's own logs
to characterize load.

`stats/docker-stats.txt`:

```text
CONTAINER ID   NAME                    CPU %    MEM USAGE / LIMIT     MEM %
b3a4...        infrahub-database-1     145.3%   12.8GiB / 14GiB       91.4%
1c2d...        infrahub-server-1       65.2%    1.1GiB / 2GiB         55.0%
8f9e...        infrahub-task-worker-1  3.1%     420MiB / 2GiB         20.5%
...
```

Combined with the baseline 24h database log
(`bundle/baseline/logs/infrahub-database-1.log`),
this is enough to see the database is hot. The
detailed Neo4j active-queries view is intentionally
not in the bundle — the skill no longer probes
inside the DB container.

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

### Step 6: Run flag checks

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

### Step 7: Redact + summary (user-gate)

The bundle contains real device names in the
database container log lines that include query
fragments. The user picks
`customer_strings=redact-all` — these are
production device hostnames they don't want
travelling.

Tier-1 already masked the database password from
`compose-resolved.yml`; the Tier-2 replacement
sweeps the device names:

```diff
-2026-05-30 13:42:09  INFO  ... Query: MATCH (n:Device) WHERE n.name = 'prod-edge-rtr-42' ...
+2026-05-30 13:42:09  INFO  ... Query: MATCH (n:Device) WHERE n.name = '***REDACTED:device***' ...
```

### Steps 8-9: Finalize + hand-off

`README.md` includes the partial-bundle note:

```text
NOTE: The user declined to share an API token, so this bundle does
not include infrahubctl state queries (branches, repos, schema,
tasks, telemetry). Topology, container logs, host fingerprint, and
local config files are present.
```

```text
Expert-ready summary:
- Infrahub 1.9.6 community (user-reported), docker-compose, single replica.
- Problem: performance — device list UI hangs > 30s.
- Got worse over the last week; no recent code/schema changes.
- Flags fired: host-low-resources.
- Host: 4 cores, 15 Gi RAM (0.7 Gi free), 100 G disk (94% used).
- docker stats: infrahub-database at 91% mem; server at 55%.
- Partial bundle: no infrahubctl state (token withheld). For deeper
  query-level analysis the user will need to provide a token.

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
- **Upgrade** had a database-pod-specific log file
  under `category/upgrade/logs/` instead of the
  prior `neo4j-report/` subtree — the skill no
  longer runs `neo4j-admin server report`.
- **Performance** ran in the token-declined path:
  no `state/` directory beyond what's still
  collectible without `infrahubctl`, no
  `telemetry.json`, no `infrahubctl branch list`
  output.

What's invariant: every example carries every
multi-replica service's logs as separate files,
the manifest mirrors the bug-report template, the
redaction report records what was masked, and the
`collected.infrahubctl_state` field in
`manifest.yml` records whether instance state was
included.
