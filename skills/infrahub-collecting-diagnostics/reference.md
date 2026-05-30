# Reference — Command Catalog

This file is the working command catalog for the
`infrahub-collecting-diagnostics` skill. Step 5 of
the workflow (targeted collection) reads from here.
Commands are read-only and safe to run against a
production Infrahub deployment.

The default log window for every command in this
file is **24 hours**, matching what OpsMill support
typically asks for. Adjust `--since` only if the
user explicitly requests a different window.

All commands assume the bundle root is the current
working directory and that `bundle/` has been
created. If a command writes a path under `bundle/`,
the parent directory must exist first — the
workflow creates them up front.

## The contract: `infrahubctl` only against the instance

Anything that probes Infrahub instance state — branches,
repositories, schemas, tasks, telemetry — uses
`infrahubctl` and nothing else.

The only stable, version-versioned contract OpsMill
commits to is `infrahubctl`. Every other path is
speculative:

- HTTP probes (`curl http://.../api/...`,
  `curl -sX POST http://.../graphql`) couple the skill
  to specific GraphQL field names and REST routes that
  shift between minor versions.
- `docker compose exec`/`kubectl exec` into stack
  containers (`cypher-shell`, `psql`, `rabbitmqctl`,
  `neo4j-admin`, `printenv`) couples the skill to
  internal implementation details (the DB engine, the
  message broker, the Prefect schema, env-var names)
  that are explicitly out of contract.

These probes worked yesterday and break tomorrow,
silently. Stick to `infrahubctl`. See
[rules/infrahubctl-only-for-instance.md](rules/infrahubctl-only-for-instance.md)
for the full rule and the live-test failures that
informed it.

Deployment-infrastructure inspection (Docker/k8s
topology, container logs, host fingerprint, file
reads of the user's local files) is **not** "the
instance" — it inspects the host and orchestration
layer the user controls, not Infrahub internals.
That is allowed and forms the rest of this catalog.

## Connection info: URL + token

Every `infrahubctl` call below assumes the workflow's
step 2 ran first and exported:

```bash
export INFRAHUB_ADDRESS="<URL the user provided>"
export INFRAHUBCTL_TOKEN="<token the user provided>"
```

The token is added to the Tier-1 redactor mask list
the moment the user shares it, so it never appears in
any bundle file — see
[rules/connection-info-and-token.md](rules/connection-info-and-token.md).

If the user declined to share a token, **every
`infrahubctl` block in this file is skipped** and
`manifest.yml` records `collected.infrahubctl_state:
false`. The topology/log/file-read collection still
runs.

## OS and shell assumptions

The skill assumes a Unix-like environment:

- **Linux** (any modern distro)
- **macOS** (12+; uses BSD `sed`/`grep` and lacks `nproc`/`free`/`sha256sum` — fallbacks below are wired in)
- **Windows** users must run from **WSL2** (Ubuntu or Debian); native `cmd.exe` and PowerShell are not supported.

The skill assumes **`bash` 4.x+** (default on Linux,
default user shell on Windows-WSL2; on macOS 10.15+
the default user shell is `zsh` but `bash` 3.2 is
present at `/bin/bash`). When the AI runs a multi-line
command block, it should invoke it explicitly as
`bash -c '<block>'` rather than letting the active
shell guess, because some compatibility helpers
(e.g., `compgen -G`) are bash-only.

**Only Docker Compose v2 is supported.** The skill
uses the `docker compose` subcommand exclusively;
legacy `docker-compose` (v1) is not a fallback. v1
reached end-of-life mid-2023 and is missing features
(notably `compose ps --format json` shape) that the
catalog relies on. If `docker compose version`
doesn't return v2.x, the workflow should ask the user
to upgrade Docker before continuing rather than
substitute v1 commands. Compose v2 has shipped by
default with Docker Desktop 4.x and Docker Engine
20.10+.

## 1. Service-name map

Canonical service names are the same across
Docker Compose and Helm. Per-topology addressing
differs.

Docker Compose container names follow the pattern
`<project>-<service>-<index>`. With the upstream
project name `infrahub`, the `infrahub-server`
service ends up as `infrahub-infrahub-server-N` (the
project prefix is repeated because the service name
itself starts with `infrahub-`). The loops below use
`docker ps --filter "name=..."` substring matching,
which catches both shapes.

| Canonical | Docker Compose container | Kubernetes label selector | Local dev (`invoke demo.*`) |
| --------- | ------------------------ | ------------------------- | --------------------------- |
| `infrahub-server` | `infrahub-infrahub-server-1`, `-2`, ... | `app.kubernetes.io/component=server` | `infrahub-infrahub-server-N` |
| `task-worker` | `infrahub-task-worker-1`, `-2`, ... | `app.kubernetes.io/component=task-worker` | `infrahub-task-worker-N` |
| `database` | `infrahub-database-1` | `app.kubernetes.io/component=database` | `infrahub-database-1` |
| `cache` | `infrahub-cache-1` | `app.kubernetes.io/component=cache` | `infrahub-cache-1` |
| `message-queue` | `infrahub-message-queue-1` | `app.kubernetes.io/component=message-queue` | `infrahub-message-queue-1` |
| `task-manager` | `infrahub-task-manager-1` | `app.kubernetes.io/component=task-manager` | `infrahub-task-manager-1` |
| `task-manager-db` | `infrahub-task-manager-db-1` | `app.kubernetes.io/component=task-manager-db` | `infrahub-task-manager-db-1` |

Multi-replica services (`infrahub-server`,
`task-worker`) need one log file per replica. The
loops below iterate `docker ps --format` /
`kubectl get pods -l` and write one file per
container/pod into `bundle/baseline/logs/` or the
relevant `bundle/category/<name>/logs/`.

## 2. Baseline collection — per topology

The baseline runs unconditionally in step 3, before
the category is known. Output paths follow the
bundle layout (see
[rules/bundle-layout.md](rules/bundle-layout.md)).

### 2.1 Docker Compose

```bash
mkdir -p bundle/baseline/{versions,deployment,config,state,logs,schemas}

# Versions (tool fingerprints)
infrahubctl version                       > bundle/baseline/versions/infrahubctl.txt 2>&1
infrahubctl info --detail                 > bundle/baseline/versions/infrahubctl-info.txt 2>&1
docker --version                          > bundle/baseline/versions/docker.txt 2>&1
docker compose version                    > bundle/baseline/versions/docker-compose.txt 2>&1
python3 --version                         > bundle/baseline/versions/python3.txt 2>&1
uname -a                                  > bundle/baseline/versions/uname.txt 2>&1

# Deployment topology
docker compose images                     > bundle/baseline/deployment/compose-images.txt 2>&1
docker compose ps -a --format json        > bundle/baseline/deployment/compose-ps.json 2>&1
docker compose top                        > bundle/baseline/deployment/compose-top.txt 2>&1
docker network ls                         > bundle/baseline/deployment/docker-networks.txt 2>&1

# Per-container inspect (resource limits, healthcheck, exit code) — host-side, not exec.
for c in $(docker compose ps -a --format '{{.Name}}'); do
  docker inspect "$c"                     > "bundle/baseline/deployment/inspect-${c}.json" 2>&1
done

# Resolved compose config — Tier-1 redactor pass required before sharing.
# This file is the source for the using-default-* flag checks (read, hash, compare).
docker compose config                     > bundle/baseline/config/compose-resolved.yml 2>&1

# User config files — copy verbatim, redactor will handle them
cp .infrahub.yml         bundle/baseline/config/  2>/dev/null || true
cp infrahub.toml         bundle/baseline/config/  2>/dev/null || true
[ -f docker-compose.yml ] && cp docker-compose.yml bundle/baseline/config/ 2>/dev/null || true

# Schema snapshot from the repo on disk (not from the server).
# sha256sum is GNU coreutils (Linux); macOS uses `shasum -a 256`.
[ -d schemas ] && cp -r schemas bundle/baseline/schemas-repo/
if [ -d schemas ]; then
  HASHER="$(command -v sha256sum || echo 'shasum -a 256')"
  (cd schemas && find . -type f -print0 | xargs -0 $HASHER) \
    > bundle/baseline/schemas-repo.sha256 2>&1
fi

# Live state — `infrahubctl` only. Skipped entirely if no token was provided.
infrahubctl branch list                   > bundle/baseline/state/branches.txt 2>&1
infrahubctl schema list                   > bundle/baseline/state/schema-kinds.txt 2>&1
infrahubctl repository list               > bundle/baseline/state/repositories.txt 2>&1
infrahubctl task list --json --limit 50   > bundle/baseline/state/recent-tasks.json 2>&1
# Note: telemetry export requires an authenticated user with permission on
# /api/telemetry/snapshots. The `|| true` keeps the bundle building when the
# call fails (403 for anonymous, missing endpoint on older builds).
infrahubctl telemetry export \
  --output bundle/baseline/state/telemetry.json   2>/dev/null || true

# Host fingerprint
{
  echo "os: \"$(uname -srm)\""
  echo "cpu_cores: $(nproc 2>/dev/null || sysctl -n hw.ncpu)"
  echo "memory_gb: $(free -g 2>/dev/null | awk '/^Mem:/ {print $2}' \
    || sysctl -n hw.memsize | awk '{printf "%.0f", $1/1024/1024/1024}')"
  echo "free_memory_gb: $(free -g 2>/dev/null | awk '/^Mem:/ {print $7}')"
  echo "disk_usage:"
  df -h | sed 's/^/  /'
} > bundle/baseline/host.yml

# 24h logs — one file per replica for multi-replica services
for c in $(docker ps --filter "name=infrahub-server" --format '{{.Names}}'); do
  docker logs --since 24h "$c"            > "bundle/baseline/logs/${c}.log" 2>&1
done
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 24h "$c"            > "bundle/baseline/logs/${c}.log" 2>&1
done
for svc in database message-queue cache task-manager task-manager-db; do
  for c in $(docker ps --filter "name=infrahub-${svc}" --format '{{.Names}}'); do
    docker logs --since 24h "$c"            > "bundle/baseline/logs/${c}.log" 2>&1
  done
done
```

### 2.2 Kubernetes

```bash
mkdir -p bundle/baseline/{versions,deployment,config,state,logs,schemas}

# Versions
infrahubctl version                       > bundle/baseline/versions/infrahubctl.txt 2>&1
infrahubctl info --detail                 > bundle/baseline/versions/infrahubctl-info.txt 2>&1
kubectl version --output=yaml             > bundle/baseline/versions/kubectl.yml 2>&1
helm version                              > bundle/baseline/versions/helm.txt 2>&1
python3 --version                         > bundle/baseline/versions/python3.txt 2>&1
uname -a                                  > bundle/baseline/versions/uname.txt 2>&1

# Deployment topology
kubectl -n infrahub get pods -o wide      > bundle/baseline/deployment/pods.txt 2>&1
kubectl -n infrahub get pods -o json      > bundle/baseline/deployment/pods.json 2>&1
kubectl -n infrahub get svc,ingress,pvc   > bundle/baseline/deployment/k8s-objects.txt 2>&1
kubectl -n infrahub get events --sort-by=.lastTimestamp \
                                          > bundle/baseline/deployment/events.txt 2>&1

# Helm-resolved values — Tier-1 redactor pass required before sharing.
# This file is the source for the using-default-* flag checks.
helm -n infrahub list                     > bundle/baseline/deployment/helm-list.txt 2>&1
helm -n infrahub get values --all infrahub \
                                          > bundle/baseline/config/helm-values.yml 2>&1

# User config files
cp .infrahub.yml         bundle/baseline/config/  2>/dev/null || true
cp infrahub.toml         bundle/baseline/config/  2>/dev/null || true

# Live state — `infrahubctl` only. INFRAHUB_ADDRESS should already point at the
# cluster's ingress / service URL; if not reachable from the host, the user
# port-forwards themselves out-of-band.
infrahubctl branch list                   > bundle/baseline/state/branches.txt 2>&1
infrahubctl schema list                   > bundle/baseline/state/schema-kinds.txt 2>&1
infrahubctl repository list               > bundle/baseline/state/repositories.txt 2>&1
infrahubctl task list --json --limit 50   > bundle/baseline/state/recent-tasks.json 2>&1
infrahubctl telemetry export \
  --output bundle/baseline/state/telemetry.json   2>/dev/null || true

# Host fingerprint — node-level on every node
kubectl get nodes -o wide                 > bundle/baseline/deployment/nodes.txt 2>&1
kubectl top nodes                         > bundle/baseline/deployment/node-resources.txt 2>&1

# 24h logs — one file per pod per component
for component in server task-worker database message-queue cache task-manager task-manager-db; do
  for pod in $(kubectl -n infrahub get pods \
    -l "app.kubernetes.io/component=${component}" \
    -o jsonpath='{.items[*].metadata.name}'); do
    kubectl -n infrahub logs --since=24h --timestamps "$pod" \
      > "bundle/baseline/logs/${pod}.log" 2>&1
    kubectl -n infrahub logs --since=24h --timestamps --previous "$pod" \
      > "bundle/baseline/logs/${pod}.previous.log" 2>/dev/null || true
  done
done
```

### 2.3 Local dev (`invoke demo.*`)

```bash
mkdir -p bundle/baseline/{versions,deployment,config,state,logs}

# Versions
infrahubctl version                       > bundle/baseline/versions/infrahubctl.txt 2>&1
infrahubctl info --detail                 > bundle/baseline/versions/infrahubctl-info.txt 2>&1
invoke --version                          > bundle/baseline/versions/invoke.txt 2>&1
docker --version                          > bundle/baseline/versions/docker.txt 2>&1
python3 --version                         > bundle/baseline/versions/python3.txt 2>&1
uname -a                                  > bundle/baseline/versions/uname.txt 2>&1

# Deployment — demo.status is the dev-mode equivalent of compose ps
invoke demo.status                        > bundle/baseline/deployment/demo-status.txt 2>&1
docker compose ps -a --format json        > bundle/baseline/deployment/compose-ps.json 2>&1

# Resolved compose config — Tier-1 redactor pass required before sharing
docker compose config                     > bundle/baseline/config/compose-resolved.yml 2>&1

# Live state via the same infrahubctl that the demo brings up
infrahubctl branch list                   > bundle/baseline/state/branches.txt 2>&1
infrahubctl schema list                   > bundle/baseline/state/schema-kinds.txt 2>&1
infrahubctl repository list               > bundle/baseline/state/repositories.txt 2>&1
infrahubctl task list --json --limit 50   > bundle/baseline/state/recent-tasks.json 2>&1
infrahubctl telemetry export \
  --output bundle/baseline/state/telemetry.json   2>/dev/null || true

# Host fingerprint — same as Compose
{
  echo "os: \"$(uname -srm)\""
  echo "cpu_cores: $(nproc 2>/dev/null || sysctl -n hw.ncpu)"
  echo "memory_gb: $(free -g 2>/dev/null | awk '/^Mem:/ {print $2}' \
    || sysctl -n hw.memsize | awk '{printf "%.0f", $1/1024/1024/1024}')"
} > bundle/baseline/host.yml

# Logs — same loops as Compose
for c in $(docker ps --filter "name=infrahub-server" --format '{{.Names}}'); do
  docker logs --since 24h "$c"            > "bundle/baseline/logs/${c}.log" 2>&1
done
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 24h "$c"            > "bundle/baseline/logs/${c}.log" 2>&1
done
for svc in database message-queue cache task-manager task-manager-db; do
  for c in $(docker ps --filter "name=infrahub-${svc}" --format '{{.Names}}'); do
    docker logs --since 24h "$c"            > "bundle/baseline/logs/${c}.log" 2>&1
  done
done
```

## 3. Category collection — per category

Every block here is run **after** the baseline.
Outputs land under `bundle/category/<name>/`.

When the user picks **everything** mode (step 4),
run every block below in sequence.

### 3.1 `installation-startup`

Containers crash on `docker compose up`; healthchecks
loop; port conflicts.

**Docker Compose:**

```bash
mkdir -p bundle/category/installation-startup/{logs,networks,inspect}

docker compose ps -a --format json        > bundle/category/installation-startup/compose-ps.json
docker compose config                     > bundle/category/installation-startup/compose-resolved.yml
docker compose top                        > bundle/category/installation-startup/compose-top.txt

# Per-container inspect (resource limits, healthcheck definition, exit code)
for c in $(docker compose ps -a --format '{{.Name}}'); do
  docker inspect "$c"                     > "bundle/category/installation-startup/inspect/${c}.json" 2>&1
done

# Network topology
docker network ls                         > bundle/category/installation-startup/networks/list.txt
for net in $(docker network ls --format '{{.Name}}' | grep -E 'infrahub|default'); do
  docker network inspect "$net"           > "bundle/category/installation-startup/networks/${net}.json" 2>&1
done

# Full-history logs (no --since cap; startup is small anyway)
for c in $(docker compose ps -a --format '{{.Name}}'); do
  docker logs "$c"                        > "bundle/category/installation-startup/logs/${c}.log" 2>&1
done
```

**Kubernetes:**

```bash
mkdir -p bundle/category/installation-startup/{describe,events,logs}

kubectl -n infrahub get pods -o wide      > bundle/category/installation-startup/pods.txt
kubectl -n infrahub get events --sort-by=.lastTimestamp \
                                          > bundle/category/installation-startup/events/all.txt

for pod in $(kubectl -n infrahub get pods -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub describe pod "$pod" > "bundle/category/installation-startup/describe/${pod}.txt"
  kubectl -n infrahub logs --timestamps   "$pod" \
                                          > "bundle/category/installation-startup/logs/${pod}.log" 2>&1
  kubectl -n infrahub logs --timestamps --previous "$pod" \
                                          > "bundle/category/installation-startup/logs/${pod}.previous.log" 2>/dev/null || true
done
```

### 3.2 `upgrade`

After `infrahub upgrade` or `helm upgrade`; branches
stuck in `NEED_UPGRADE_REBASE`.

**Docker Compose:**

```bash
mkdir -p bundle/category/upgrade/{logs,branches}

# Image SHAs reveal what version is actually running per service
docker compose images                     > bundle/category/upgrade/compose-images.txt

# 24h logs from every service — upgrade-specific runs unbounded across all of them
for c in $(docker compose ps -a --format '{{.Name}}'); do
  docker logs --since 24h "$c"            > "bundle/category/upgrade/logs/${c}.log" 2>&1
done

# Focused database container logs — surfaces migration / startup errors from Neo4j or Memgraph
# (no infrahubctl wrapper — relying on logs and topology only)
for c in $(docker ps --filter "name=infrahub-database" --format '{{.Names}}'); do
  docker logs --since 24h "$c"            > "bundle/category/upgrade/logs/${c}.log" 2>&1
done

# Branches in stuck states — text output from infrahubctl is the source of truth.
infrahubctl branch list                   > bundle/category/upgrade/branches/list.txt 2>&1
```

**Kubernetes:**

```bash
mkdir -p bundle/category/upgrade/{logs,branches}

kubectl -n infrahub get pods -o yaml      > bundle/category/upgrade/pods-yaml.txt
helm -n infrahub history infrahub         > bundle/category/upgrade/helm-history.txt 2>&1

for pod in $(kubectl -n infrahub get pods -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=24h --timestamps "$pod" \
                                          > "bundle/category/upgrade/logs/${pod}.log" 2>&1
done

# Database pod logs explicitly — migration errors land here
for pod in $(kubectl -n infrahub get pods -l app.kubernetes.io/component=database \
  -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=24h --timestamps "$pod" \
                                          > "bundle/category/upgrade/logs/${pod}-database.log" 2>&1
done

infrahubctl branch list                   > bundle/category/upgrade/branches/list.txt 2>&1
```

### 3.3 `git-sync`

Repo state `Error`/`Unknown`; `CommitNotFoundError`;
schemas not loaded from repo.

**Docker Compose:**

```bash
mkdir -p bundle/category/git-sync/{config,logs}

# Copy the user's .infrahub.yml so the expert can see what was expected
cp .infrahub.yml bundle/category/git-sync/config/ 2>/dev/null || true

# 1h focused logs from every task-worker replica — multi-worker race conditions
# (#9036, #9293) hide when only one replica is sampled. The traceback for
# CommitNotFoundError and Permission denied (publickey) lands here.
# (no infrahubctl wrapper for per-worker git state — relying on logs only)
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 1h "$c" \
                                          > "bundle/category/git-sync/logs/${c}.log" 2>&1
done

# Repository state from the server's point of view — infrahubctl only.
infrahubctl repository list               > bundle/category/git-sync/repositories.txt 2>&1
```

**Kubernetes:**

```bash
mkdir -p bundle/category/git-sync/{config,logs}

cp .infrahub.yml bundle/category/git-sync/config/ 2>/dev/null || true

for pod in $(kubectl -n infrahub get pods \
  -l app.kubernetes.io/component=task-worker \
  -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=1h --timestamps "$pod" \
                                          > "bundle/category/git-sync/logs/${pod}.log" 2>&1
done

infrahubctl repository list               > bundle/category/git-sync/repositories.txt 2>&1
```

### 3.4 `task-worker-pipeline`

Tasks stuck `RUNNING`/`MERGING`; worker
CrashLoopBackOff; proposed-change pipeline never
completes.

**Docker Compose:**

```bash
mkdir -p bundle/category/task-worker-pipeline/logs

# Failed / crashed / hung tasks with full logs — `--json` is supported on
# `infrahubctl task list`. -s filters stack: list each state to include.
infrahubctl task list --include-logs --json \
  -s FAILED -s CRASHED -s RUNNING         > bundle/category/task-worker-pipeline/failed-tasks.json 2>&1

# Recent tasks with related-nodes context
infrahubctl task list --include-related-nodes --json --limit 200 \
                                          > bundle/category/task-worker-pipeline/recent-tasks.json 2>&1

# 2h focused worker + task-manager logs (heavier than baseline 24h sample).
# Queue depths and Prefect flow-run state live inside the message-queue and
# task-manager-db containers respectively; this skill no longer reaches inside
# them. The worker + task-manager logs report the same symptoms one layer up.
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 2h "$c"             > "bundle/category/task-worker-pipeline/logs/${c}.log" 2>&1
done
docker compose logs --since 2h --no-color task-manager \
                                          > bundle/category/task-worker-pipeline/logs/task-manager.log 2>&1
docker compose logs --since 2h --no-color message-queue \
                                          > bundle/category/task-worker-pipeline/logs/message-queue.log 2>&1
```

**Kubernetes:**

```bash
mkdir -p bundle/category/task-worker-pipeline/logs

infrahubctl task list --include-logs --json \
  -s FAILED -s CRASHED -s RUNNING         > bundle/category/task-worker-pipeline/failed-tasks.json 2>&1
infrahubctl task list --include-related-nodes --json --limit 200 \
                                          > bundle/category/task-worker-pipeline/recent-tasks.json 2>&1

for pod in $(kubectl -n infrahub get pods \
  -l app.kubernetes.io/component=task-worker \
  -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=2h --timestamps "$pod" \
                                          > "bundle/category/task-worker-pipeline/logs/${pod}.log" 2>&1
done

# Task-manager + message-queue logs — same role as the compose block above
for component in task-manager message-queue; do
  for pod in $(kubectl -n infrahub get pods \
    -l "app.kubernetes.io/component=${component}" \
    -o jsonpath='{.items[*].metadata.name}'); do
    kubectl -n infrahub logs --since=2h --timestamps "$pod" \
                                          > "bundle/category/task-worker-pipeline/logs/${pod}.log" 2>&1
  done
done
```

### 3.5 `schema-load`

`schema check` rejects file; `/api/schema/load`
hangs; schema-load failures.

```bash
mkdir -p bundle/category/schema-load/{check,export} bundle/repro/schemas

# Validate the user's schemas — surfaces compliance failures without touching server.
# Use a portable existence check (compgen is bash-only).
if ls schemas/*.yml > /dev/null 2>&1; then
  infrahubctl schema check schemas/*.yml  > bundle/category/schema-load/check/output.txt 2>&1 || true
  cp -r schemas bundle/repro/
fi

# Server-side authoritative schema
infrahubctl schema export \
  --directory bundle/category/schema-load/export/   2>&1 \
  | tee bundle/category/schema-load/export/run.log
infrahubctl schema list                   > bundle/category/schema-load/kinds.txt 2>&1

# 30m server logs filtered to schema activity
docker compose logs --since 30m --no-color infrahub-server 2>&1 \
  | grep -iE 'schema|load|migration' \
                                          > bundle/category/schema-load/server-schema.log
```

For Kubernetes, replace the `docker compose logs`
line with:

```bash
for pod in $(kubectl -n infrahub get pods -l app.kubernetes.io/component=server \
  -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=30m --timestamps "$pod" 2>&1 \
    | grep -iE 'schema|load|migration' \
                                          > "bundle/category/schema-load/${pod}-schema.log"
done
```

### 3.6 `check-generator-transform`

Pipeline check red; `infrahubctl <kind>` raises;
Jinja2 transform fails.

```bash
mkdir -p bundle/repro/{checks,generators,transforms,queries,runs} \
         bundle/category/check-generator-transform/{logs,output}

# Source files — copy as-is, redactor will sweep them
cp .infrahub.yml bundle/repro/ 2>/dev/null || true
for d in checks generators transforms queries; do
  [ -d "$d" ] && cp -r "$d" bundle/repro/
done

# Reproduce the failure locally — exit code preserved in output
# (the workflow asks the user which name to reproduce; templates below)
# infrahubctl check     <name> > bundle/repro/runs/check-<name>.txt     2>&1
# infrahubctl generator <name> > bundle/repro/runs/generator-<name>.txt 2>&1
# infrahubctl render    <name> > bundle/repro/runs/render-<name>.txt    2>&1
# infrahubctl transform <name> > bundle/repro/runs/transform-<name>.txt 2>&1

# 1h focused worker logs — where the in-pipeline failure prints its traceback
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 1h "$c"             > "bundle/category/check-generator-transform/logs/${c}.log" 2>&1
done
```

### 3.7 `graphql-api`

HTTP 5xx; non-nullable field errors; timeouts.

```bash
mkdir -p bundle/category/graphql-api/logs bundle/repro

# The user pastes the failing query into bundle/repro/failing.gql for the
# expert to reproduce — the skill itself does not run ad-hoc GraphQL queries.
# (no infrahubctl wrapper for ad-hoc query execution — paste-only)

# 15m server logs
docker compose logs --since 15m --no-color infrahub-server \
                                          > bundle/category/graphql-api/logs/infrahub-server.log 2>&1

# Note: To capture detailed query timing, set
#   INFRAHUB_MISC_PRINT_QUERY_DETAILS=true on the server
#   INFRAHUB_ECHO_GRAPHQL_QUERIES=true     on the SDK side
# Both require a process restart by the user — this skill never restarts services.
# Document the setting in bundle/category/graphql-api/README.txt instead.
cat > bundle/category/graphql-api/README.txt <<'EOF'
For a follow-up run, the user can opt in to verbose query logging:

  Server-side: INFRAHUB_MISC_PRINT_QUERY_DETAILS=true
               (requires restarting infrahub-server)
  Client-side: INFRAHUB_ECHO_GRAPHQL_QUERIES=true
               (no restart; SDK-level setting)

The skill does not restart the server; the user must do that themselves
before re-collecting if they want the verbose logs.

If you want to attach the failing query and the server's response, paste
the query body into bundle/repro/failing.gql and (optionally) the response
JSON into bundle/repro/graphql-response.json. The skill itself does not
issue ad-hoc GraphQL POSTs.
EOF
```

### 3.8 `performance`

Slow UI, slow diff, OOM kills, browser hangs on
large nodes.

**Docker Compose:**

```bash
mkdir -p bundle/category/performance/{stats,host}

# Container resource use right now — host-side, no exec into stack containers
docker stats --no-stream                  > bundle/category/performance/stats/docker-stats.txt 2>&1

# Telemetry — has per-endpoint timings (infrahubctl only)
infrahubctl telemetry export \
  --output bundle/category/performance/telemetry.json   2>/dev/null || true

# Host resources
{
  echo "--- nproc ---"; nproc 2>/dev/null || sysctl -n hw.ncpu
  echo "--- free -h ---"; free -h 2>/dev/null || vm_stat
  echo "--- df -h ---"; df -h
  echo "--- uptime ---"; uptime
} > bundle/category/performance/host/resources.txt
```

**Kubernetes:**

```bash
mkdir -p bundle/category/performance/{stats,host}

# Per-pod resource use
kubectl -n infrahub top pods              > bundle/category/performance/stats/pod-resources.txt 2>&1
kubectl top nodes                         > bundle/category/performance/stats/node-resources.txt 2>&1

infrahubctl telemetry export \
  --output bundle/category/performance/telemetry.json   2>/dev/null || true
```

### 3.9 `auth-permissions`

OAuth/OIDC login fails; default role can't create
proposed change; JWT mismatch.

```bash
mkdir -p bundle/category/auth-permissions/{config,logs}

# SSO-related config comes from the resolved compose / helm values file we
# already collected in the baseline — we do not exec inside the server
# container to print env. The redactor masks INFRAHUB_*_SECRET / *_TOKEN /
# *_PASSWORD values before the bundle is finalized.
{
  echo "Auth-related keys from the resolved deployment config (already collected"
  echo "into bundle/baseline/config/compose-resolved.yml or helm-values.yml)."
  echo "The Tier-1 redactor masks secret values before the bundle is finalized."
} > bundle/category/auth-permissions/config/README.txt

# 30m server logs filtered to auth lines
docker compose logs --since 30m --no-color infrahub-server 2>&1 \
  | grep -iE 'auth|token|oauth|oidc|permission' \
                                          > bundle/category/auth-permissions/logs/server-auth.log
```

For Kubernetes:

```bash
mkdir -p bundle/category/auth-permissions/{config,logs}

cat > bundle/category/auth-permissions/config/README.txt <<'EOF'
Auth-related keys from the resolved helm values are in
bundle/baseline/config/helm-values.yml. Secret values are masked by the
Tier-1 redactor before the bundle is finalized.
EOF

for pod in $(kubectl -n infrahub get pods -l app.kubernetes.io/component=server \
  -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=30m --timestamps "$pod" 2>&1 \
    | grep -iE 'auth|token|oauth|oidc|permission' \
                                          > "bundle/category/auth-permissions/logs/${pod}-auth.log"
done
```

### 3.10 `branch-merge`

Branch stuck `MERGING`/`DELETING`; failed merge
leaves partial state.

```bash
mkdir -p bundle/category/branch-merge/branches

# Branch state — `infrahubctl` only.
infrahubctl branch list                   > bundle/category/branch-merge/branches/list.txt 2>&1

# Per-branch detailed report. `infrahubctl branch report` requires a branch
# name; iterate the names from `branch list` (text parsing is fine — the
# output is stable per-version).
for b in $(awk 'NR>1 {print $1}' bundle/category/branch-merge/branches/list.txt 2>/dev/null \
            | grep -vE '^(main|\-+|NAME|$)'); do
  infrahubctl branch report "$b" \
                                          > "bundle/category/branch-merge/branches/report-${b}.txt" 2>&1 || true
done

# Prompt the user to export filtered activity CSV from the UI:
#   Open <infrahub-url>/activities, filter to "Branch", "Merge", "Delete"
#   actions, export CSV, drop file at bundle/category/branch-merge/activities.csv
cat > bundle/category/branch-merge/activities.README.txt <<'EOF'
Export the activity log filtered to Branch / Merge / Delete events from the UI
(navigate to /activities, apply the filter, click Export CSV) and save the file
at bundle/category/branch-merge/activities.csv.
EOF
```

Kubernetes is identical — every command above is
`infrahubctl` and works regardless of topology, given
that `INFRAHUB_ADDRESS` reaches the cluster (the user
sets that up out-of-band — see step 2 in the
workflow).

## 4. Environment variable catalog

Diagnostic-relevant `INFRAHUB_*` variables. The
"Masked" column shows whether the Tier-1 redactor
strips the value before the bundle is written.

This is documentation, not a probe — the skill does
not run `env` or `printenv` inside any Infrahub
container. The skill reads the resolved deployment
config (`compose-resolved.yml` /
`helm-values.yml`) for any variable it needs to
inspect (see the `using-default-*` flag checks).

| Variable | Default | What it tells you when present | Masked |
| -------- | ------- | ------------------------------ | ------ |
| `INFRAHUB_LOG_LEVEL` | `INFO` | Log verbosity. Lower than `INFO` (`DEBUG`, `TRACE`) means logs are noisier and may include payloads. | No |
| `INFRAHUB_ECHO_GRAPHQL_QUERIES` | unset | SDK-side echo of every GraphQL query the Python SDK sends. | No |
| `INFRAHUB_MISC_PRINT_QUERY_DETAILS` | unset | Server-side detailed query logging (timing + parameters). Requires a server restart by the user. | No |
| `INFRAHUB_WORKFLOW_EXTRA_LOGGERS` | unset | Comma-separated logger names that get bumped to `INFRAHUB_WORKFLOW_EXTRA_LOG_LEVEL`. Used to bump per-task verbosity. | No |
| `INFRAHUB_WORKFLOW_EXTRA_LOG_LEVEL` | unset | Level applied to the loggers in the variable above. | No |
| `INFRAHUB_DB_TYPE` | `neo4j` | Database backend. `neo4j` or `memgraph`. | No |
| `INFRAHUB_TELEMETRY_OPTOUT` | unset (telemetry on) | When set to `true`, suppresses anonymous telemetry. The skill skips `infrahubctl telemetry export` when this is set. | No |
| `INFRAHUB_SECURITY_SECRET_KEY` | (compose default) | JWT signing key. Multi-pod JWT-mismatch bugs ([#8925](https://github.com/opsmill/infrahub/issues/8925)) hinge on whether the documented default is in use. | Yes — manifest records `using_default_security_key` by hash comparison |
| `INFRAHUB_INITIAL_ADMIN_TOKEN` | (compose default) | Bootstrap admin token. | Yes — manifest records `using_default_init_token` |
| `INFRAHUB_INITIAL_AGENT_TOKEN` | (compose default) | Agent token for task workers. | Yes |
| `INFRAHUB_API_TOKEN` | unset | SDK auth token. | Yes |
| `INFRAHUB_BROKER_PASSWORD` | (compose default) | RabbitMQ password. | Yes |
| `INFRAHUB_CACHE_PASSWORD` | (compose default) | Redis password. | Yes |
| `INFRAHUB_TASKMANAGER_DB_PASSWORD` | (compose default) | Prefect Postgres password. | Yes |
| `INFRAHUB_DB_PASSWORD` | (compose default) | Neo4j or Memgraph password. | Yes |

Authoritative source:
[docs.infrahub.app — Configuration reference](https://docs.infrahub.app/reference/configuration).

## 5. `/api/config` — optional, user-paste only

`/api/config` is the server's own health and identity
endpoint. The upstream `docker-compose.yml` uses it
as the healthcheck target, so any working deployment
returns it. The skill **does not** call this
endpoint itself — see the contract at the top of this
file. If the user wants the server's own
version self-report in the bundle, they can run the
request themselves and paste the JSON into
`bundle/baseline/api-config.json`:

```bash
# Run by the user, out-of-band — NOT by this skill:
#   curl -sf "$INFRAHUB_ADDRESS/api/config" > bundle/baseline/api-config.json
```

The skill relies on `infrahubctl version` and
`infrahubctl info --detail` for the version/edition
fields in `manifest.yml` — both are first-party
contract.

Example response (truncated to the diagnostic-
relevant fields):

```json
{
  "main": {
    "internal_address": "http://localhost:8000",
    "allow_anonymous_access": true,
    "telemetry_optout": false
  },
  "version": {
    "version": "1.9.6",
    "edition": "community"
  },
  "experimental_features": {
    "ipam": true
  }
}
```

If the user does paste this file, key fields to
extract into `manifest.yml`:

| Field | Manifest target |
| ----- | --------------- |
| `version.version` | `infrahub.version` (cross-check vs `infrahubctl version`) |
| `version.edition` | `infrahub.edition` |
| `version.build_sha` (if present) | `infrahub.build_sha` |

## 6. `manifest.yml` schema (canonical)

The canonical schema with every required key. Mirror
this exactly when generating `bundle/manifest.yml`.

```yaml
bundle_version: "1.0"
generated_at: "2026-05-30T12:00:00Z"
skill_version: "1.2.5"               # from .claude-plugin/plugin.json
infrahub:
  version: "1.9.6"                   # from `infrahubctl version` (or /api/config if user pasted it)
  edition: "community"               # community | enterprise
  using_default_security_key: false  # hash compare against compose-resolved.yml / helm-values.yml
  using_default_init_token: false
  # Optional — only present when client and server self-report disagree
  client_version: "1.8.2"            # from `infrahubctl version`
  version_mismatch: false
deployment:
  topology: "docker-compose"         # docker-compose | kubernetes | local-dev | manual
  worker_replicas: 2
  image_shas:
    infrahub-server: "sha256:..."
    task-worker: "sha256:..."
host:
  os: "Linux 6.x"
  cpu_cores: 8
  memory_gb: 16
problem:
  # Mirrors opsmill/infrahub bug-report template verbatim
  component: "Git Integration"       # Frontend UI | API Server | Git Integration
                                     # | Python SDK | infrahubctl CLI | Not Sure
  current_behavior: "..."
  expected_behavior: "..."
  steps_to_reproduce: "..."
  error_message: "..."
  first_observed: "2026-05-29"
  reproducible: true
  impact: "blocker"                  # blocker | major | minor
  category: "git-sync"               # one of the 10 categories or "unknown"
collected:
  baseline: true
  category_dirs: ["git-sync"]
  repro_included: true
  multi_replica_coverage: true
  infrahubctl_state: true            # false when the user declined to share a token
redaction:
  applied: true
  rules_version: "1.0"
  files_touched: 47
  replacements: 192
  user_review_completed: true
  user_choices:
    public_ips: "redact-all"         # keep | redact-all | case-by-case
    hostnames: "keep"
    customer_strings: "redact-all"
```

Every top-level key (`bundle_version`,
`generated_at`, `skill_version`, `infrahub`,
`deployment`, `host`, `problem`, `collected`,
`redaction`) is required. See
[rules/manifest-template.md](rules/manifest-template.md)
for the field-by-field contract and version
cross-check rules.
