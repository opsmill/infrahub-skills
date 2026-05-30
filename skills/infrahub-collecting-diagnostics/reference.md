# Reference — Command Catalog

This file is the working command catalog for the
`infrahub-collecting-diagnostics` skill. Step 4 of
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

## 1. Service-name map

Canonical service names are the same across
Docker Compose and Helm. Per-topology addressing
differs.

| Canonical | Docker Compose container | Kubernetes label selector | Local dev (`invoke demo.*`) |
| --------- | ------------------------ | ------------------------- | --------------------------- |
| `infrahub-server` | `infrahub-server-1`, `-2`, ... | `app.kubernetes.io/component=server` | `infrahub-server-N` |
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

The baseline runs unconditionally in step 2, before
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

# Resolved compose config — Tier-1 redactor pass required before sharing
docker compose config                     > bundle/baseline/config/compose-resolved.yml 2>&1

# User config files — copy verbatim, redactor will handle them
cp .infrahub.yml         bundle/baseline/config/  2>/dev/null || true
cp infrahub.toml         bundle/baseline/config/  2>/dev/null || true

# Server self-report — version + edition + build SHA when present
curl -sf http://localhost:8000/api/config > bundle/baseline/api-config.json 2>&1

# Schema snapshot from the repo on disk (not from the server)
[ -d schemas ] && cp -r schemas bundle/baseline/schemas-repo/
[ -d schemas ] && (cd schemas && find . -type f -print0 | xargs -0 sha256sum) \
  > bundle/baseline/schemas-repo.sha256 2>&1

# Live state (read-only)
infrahubctl branch list --json            > bundle/baseline/state/branches.json 2>&1
infrahubctl schema list                   > bundle/baseline/state/schema-kinds.txt 2>&1
infrahubctl repository list               > bundle/baseline/state/repositories.txt 2>&1
infrahubctl task list --json --limit 50   > bundle/baseline/state/recent-tasks.json 2>&1
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
  docker logs --since 24h --no-color "$c" > "bundle/baseline/logs/${c}.log" 2>&1
done
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 24h --no-color "$c" > "bundle/baseline/logs/${c}.log" 2>&1
done
for svc in database message-queue cache task-manager task-manager-db; do
  for c in $(docker ps --filter "name=infrahub-${svc}" --format '{{.Names}}'); do
    docker logs --since 24h --no-color "$c" > "bundle/baseline/logs/${c}.log" 2>&1
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

# Helm-resolved values — Tier-1 redactor pass required before sharing
helm -n infrahub list                     > bundle/baseline/deployment/helm-list.txt 2>&1
helm -n infrahub get values --all infrahub \
                                          > bundle/baseline/config/helm-values.yml 2>&1

# User config files
cp .infrahub.yml         bundle/baseline/config/  2>/dev/null || true
cp infrahub.toml         bundle/baseline/config/  2>/dev/null || true

# Server self-report — port-forward if no Ingress
kubectl -n infrahub port-forward svc/infrahub-server 8000:8000 \
  > /dev/null 2>&1 &
PF_PID=$!
sleep 2
curl -sf http://localhost:8000/api/config > bundle/baseline/api-config.json 2>&1
kill $PF_PID 2>/dev/null || true

# Live state
infrahubctl branch list --json            > bundle/baseline/state/branches.json 2>&1
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

# Server self-report
curl -sf http://localhost:8000/api/config > bundle/baseline/api-config.json 2>&1

# Live state via the same infrahubctl that the demo brings up
infrahubctl branch list --json            > bundle/baseline/state/branches.json 2>&1
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
  docker logs --since 24h --no-color "$c" > "bundle/baseline/logs/${c}.log" 2>&1
done
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 24h --no-color "$c" > "bundle/baseline/logs/${c}.log" 2>&1
done
for svc in database message-queue cache task-manager task-manager-db; do
  for c in $(docker ps --filter "name=infrahub-${svc}" --format '{{.Names}}'); do
    docker logs --since 24h --no-color "$c" > "bundle/baseline/logs/${c}.log" 2>&1
  done
done
```

## 3. Category collection — per category

Every block here is run **after** the baseline.
Outputs land under `bundle/category/<name>/`.

When the user picks **everything** mode (step 3),
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
  docker logs --no-color "$c"             > "bundle/category/installation-startup/logs/${c}.log" 2>&1
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
mkdir -p bundle/category/upgrade/{logs,neo4j-report,branches}

# Image SHAs reveal what version is actually running per service
docker compose images                     > bundle/category/upgrade/compose-images.txt

# 24h logs from every service — upgrade-specific runs unbounded across all of them
for c in $(docker compose ps -a --format '{{.Name}}'); do
  docker logs --since 24h --no-color "$c" > "bundle/category/upgrade/logs/${c}.log" 2>&1
done

# Neo4j health report — bundled tool, writes a single tgz
docker compose exec -T database \
  neo4j-admin server report --to-path=/tmp/ 2>&1 \
  | tee bundle/category/upgrade/neo4j-report/run.log

# Copy the report tgz out to the bundle
docker compose cp database:/tmp/. bundle/category/upgrade/neo4j-report/ 2>/dev/null || true

# Branches in stuck states
infrahubctl branch list --json            > bundle/category/upgrade/branches/list.json
# Filter for stuck branches (informational; raw list is the source of truth)
infrahubctl branch list --json \
  | python3 -c 'import json,sys; \
  data = json.load(sys.stdin); \
  print(json.dumps([b for b in data \
    if b.get("status") in ("NEED_UPGRADE_REBASE","MERGING")], indent=2))' \
                                          > bundle/category/upgrade/branches/stuck.json 2>&1
```

**Kubernetes:**

```bash
mkdir -p bundle/category/upgrade/{logs,neo4j-report,branches}

kubectl -n infrahub get pods -o yaml      > bundle/category/upgrade/pods-yaml.txt
helm -n infrahub history infrahub         > bundle/category/upgrade/helm-history.txt 2>&1

for pod in $(kubectl -n infrahub get pods -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n infrahub logs --since=24h --timestamps "$pod" \
                                          > "bundle/category/upgrade/logs/${pod}.log" 2>&1
done

# Neo4j health report from the database pod
DB_POD=$(kubectl -n infrahub get pods -l app.kubernetes.io/component=database \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n infrahub exec "$DB_POD" -- \
  neo4j-admin server report --to-path=/tmp/ 2>&1 \
  | tee bundle/category/upgrade/neo4j-report/run.log
kubectl -n infrahub cp "${DB_POD}:/tmp" bundle/category/upgrade/neo4j-report/ 2>/dev/null || true

infrahubctl branch list --json            > bundle/category/upgrade/branches/list.json
```

### 3.3 `git-sync`

Repo state `Error`/`Unknown`; `CommitNotFoundError`;
schemas not loaded from repo.

**Docker Compose:**

```bash
mkdir -p bundle/category/git-sync/{workers,repos-graphql,config}

# Copy the user's .infrahub.yml so the expert can see what was expected
cp .infrahub.yml bundle/category/git-sync/config/ 2>/dev/null || true

# Per-worker /opt/infrahub/git inspection — every replica
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  mkdir -p "bundle/category/git-sync/workers/${c}"
  docker exec "$c" ls -la /opt/infrahub/git \
                                          > "bundle/category/git-sync/workers/${c}/git-dir-listing.txt" 2>&1
  docker exec "$c" sh -c 'for d in /opt/infrahub/git/*/; do
    [ -d "$d/.git" ] || continue
    echo "===== $d ====="
    cd "$d" && git status --short --branch
    echo
    echo "--- recent commits ---"
    git log --oneline -10
    echo
    echo "--- remote ---"
    git remote -v
    echo
  done'                                   > "bundle/category/git-sync/workers/${c}/repo-status.txt" 2>&1
  # 1h focused logs from this worker
  docker logs --since 1h --no-color "$c" \
                                          > "bundle/category/git-sync/workers/${c}/recent.log" 2>&1
done

# Repository state from the server's point of view
infrahubctl repository list               > bundle/category/git-sync/repositories.txt 2>&1
infrahubctl graphql --query 'query {
  CoreGenericRepository {
    edges {
      node {
        id
        name { value }
        location { value }
        commit { value }
        status { value }
        operational_status { value }
      }
    }
  }
}'                                        > bundle/category/git-sync/repos-graphql.json 2>&1
```

**Kubernetes:**

```bash
mkdir -p bundle/category/git-sync/{workers,repos-graphql,config}

cp .infrahub.yml bundle/category/git-sync/config/ 2>/dev/null || true

for pod in $(kubectl -n infrahub get pods \
  -l app.kubernetes.io/component=task-worker \
  -o jsonpath='{.items[*].metadata.name}'); do
  mkdir -p "bundle/category/git-sync/workers/${pod}"
  kubectl -n infrahub exec "$pod" -- ls -la /opt/infrahub/git \
                                          > "bundle/category/git-sync/workers/${pod}/git-dir-listing.txt" 2>&1
  kubectl -n infrahub exec "$pod" -- sh -c 'for d in /opt/infrahub/git/*/; do
    [ -d "$d/.git" ] || continue
    echo "===== $d ====="
    cd "$d" && git status --short --branch
    echo "--- recent commits ---"; git log --oneline -10
    echo "--- remote ---"; git remote -v
  done'                                   > "bundle/category/git-sync/workers/${pod}/repo-status.txt" 2>&1
  kubectl -n infrahub logs --since=1h --timestamps "$pod" \
                                          > "bundle/category/git-sync/workers/${pod}/recent.log" 2>&1
done

infrahubctl repository list               > bundle/category/git-sync/repositories.txt 2>&1
infrahubctl graphql --query 'query {
  CoreGenericRepository {
    edges { node { id name { value } location { value } commit { value }
      status { value } operational_status { value } } }
  }
}'                                        > bundle/category/git-sync/repos-graphql.json 2>&1
```

### 3.4 `task-worker-pipeline`

Tasks stuck `RUNNING`/`MERGING`; worker
CrashLoopBackOff; proposed-change pipeline never
completes.

**Docker Compose:**

```bash
mkdir -p bundle/category/task-worker-pipeline/{logs,prefect,rabbitmq}

# Failed / crashed / hung tasks with full logs
infrahubctl task list --include-logs --json \
  -s FAILED -s CRASHED -s RUNNING         > bundle/category/task-worker-pipeline/failed-tasks.json 2>&1

# Recent tasks with related-nodes context
infrahubctl task list --include-related-nodes --json --limit 200 \
                                          > bundle/category/task-worker-pipeline/recent-tasks.json 2>&1

# 2h focused worker + task-manager logs (heavier than baseline 24h sample)
for c in $(docker ps --filter "name=task-worker" --format '{{.Names}}'); do
  docker logs --since 2h --no-color "$c"  > "bundle/category/task-worker-pipeline/logs/${c}.log" 2>&1
done
docker compose logs --since 2h --no-color task-manager \
                                          > bundle/category/task-worker-pipeline/logs/task-manager.log 2>&1

# Prefect flow-run state via task-manager-db (Postgres)
docker compose exec -T task-manager-db psql -U postgres -d prefect -c \
  "SELECT id, name, state_type, state_name, start_time, end_time
   FROM flow_run ORDER BY start_time DESC LIMIT 50;" \
                                          > bundle/category/task-worker-pipeline/prefect/recent-runs.txt 2>&1

# RabbitMQ queue depths — non-empty queues are the smoking gun
docker compose exec -T message-queue \
  rabbitmqctl list_queues name messages consumers \
                                          > bundle/category/task-worker-pipeline/rabbitmq/queues.txt 2>&1
docker compose exec -T message-queue \
  rabbitmqctl list_consumers              > bundle/category/task-worker-pipeline/rabbitmq/consumers.txt 2>&1
```

**Kubernetes:**

```bash
mkdir -p bundle/category/task-worker-pipeline/{logs,prefect,rabbitmq}

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

TM_DB=$(kubectl -n infrahub get pods -l app.kubernetes.io/component=task-manager-db \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n infrahub exec "$TM_DB" -- psql -U postgres -d prefect -c \
  "SELECT id, name, state_type, state_name, start_time, end_time
   FROM flow_run ORDER BY start_time DESC LIMIT 50;" \
                                          > bundle/category/task-worker-pipeline/prefect/recent-runs.txt 2>&1

MQ=$(kubectl -n infrahub get pods -l app.kubernetes.io/component=message-queue \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n infrahub exec "$MQ" -- rabbitmqctl list_queues name messages consumers \
                                          > bundle/category/task-worker-pipeline/rabbitmq/queues.txt 2>&1
```

### 3.5 `schema-load`

`schema check` rejects file; `/api/schema/load`
hangs; schema hash drift between workers.

```bash
mkdir -p bundle/category/schema-load/{check,export,summary} bundle/repro/schemas

# Validate the user's schemas — surfaces compliance failures without touching server
if compgen -G "schemas/*.yml" > /dev/null; then
  infrahubctl schema check schemas/*.yml  > bundle/category/schema-load/check/output.txt 2>&1 || true
  cp -r schemas bundle/repro/
fi

# Server-side authoritative schema
infrahubctl schema export \
  --directory bundle/category/schema-load/export/   2>&1 \
  | tee bundle/category/schema-load/export/run.log
infrahubctl schema list                   > bundle/category/schema-load/kinds.txt 2>&1

# Summary endpoint — hash field is the schema-hash-drift signal
curl -sf http://localhost:8000/api/schema/summary \
                                          > bundle/category/schema-load/summary/main.json 2>&1

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
  docker logs --since 1h --no-color "$c"  > "bundle/category/check-generator-transform/logs/${c}.log" 2>&1
done
```

### 3.7 `graphql-api`

HTTP 5xx; non-nullable field errors; timeouts.

```bash
mkdir -p bundle/category/graphql-api/{logs,response} bundle/repro

# User pastes the failing query into bundle/repro/failing.gql first.
# Then run it via infrahubctl so the response is captured verbatim.
if [ -f bundle/repro/failing.gql ]; then
  infrahubctl graphql --query "$(cat bundle/repro/failing.gql)" \
                                          > bundle/repro/graphql-response.json 2>&1 || true
fi

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
EOF
```

### 3.8 `performance`

Slow UI, slow diff, OOM kills, browser hangs on
large nodes.

**Docker Compose:**

```bash
mkdir -p bundle/category/performance/{stats,neo4j,host}

# Container resource use right now
docker stats --no-stream                  > bundle/category/performance/stats/docker-stats.txt 2>&1

# Neo4j active queries — the long ones are the smoking gun
docker compose exec -T database cypher-shell -u neo4j \
  -p "$INFRAHUB_DB_PASSWORD" \
  "CALL dbms.listQueries() YIELD query, elapsedTimeMillis
   RETURN query, elapsedTimeMillis ORDER BY elapsedTimeMillis DESC LIMIT 50;" \
                                          > bundle/category/performance/neo4j/active-queries.txt 2>&1

# Telemetry — has per-endpoint timings
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
mkdir -p bundle/category/performance/{stats,neo4j,host}

# Per-pod resource use
kubectl -n infrahub top pods              > bundle/category/performance/stats/pod-resources.txt 2>&1
kubectl top nodes                         > bundle/category/performance/stats/node-resources.txt 2>&1

DB_POD=$(kubectl -n infrahub get pods -l app.kubernetes.io/component=database \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n infrahub exec "$DB_POD" -- cypher-shell -u neo4j \
  -p "$INFRAHUB_DB_PASSWORD" \
  "CALL dbms.listQueries() YIELD query, elapsedTimeMillis
   RETURN query, elapsedTimeMillis ORDER BY elapsedTimeMillis DESC LIMIT 50;" \
                                          > bundle/category/performance/neo4j/active-queries.txt 2>&1

infrahubctl telemetry export \
  --output bundle/category/performance/telemetry.json   2>/dev/null || true
```

### 3.9 `auth-permissions`

OAuth/OIDC login fails; default role can't create
proposed change; JWT mismatch.

```bash
mkdir -p bundle/category/auth-permissions/{env,logs,accounts}

# SSO-related env — masked inline before writing to disk
docker compose exec -T infrahub-server env \
  | grep -E '^INFRAHUB_(SECURITY|OAUTH2|OIDC)_' \
  | sed -E 's/(SECRET|TOKEN|PASSWORD)[^=]*=.*/\1=***REDACTED***/' \
                                          > bundle/category/auth-permissions/env/sso-vars.txt 2>&1

# 30m server logs filtered to auth lines
docker compose logs --since 30m --no-color infrahub-server 2>&1 \
  | grep -iE 'auth|token|oauth|oidc|permission' \
                                          > bundle/category/auth-permissions/logs/server-auth.log

# Account inventory — who exists, what role, what account_type
infrahubctl graphql --query 'query {
  CoreAccount {
    count
    edges {
      node {
        id
        name { value }
        account_type { value }
        role { node { name { value } } }
      }
    }
  }
}'                                        > bundle/category/auth-permissions/accounts/inventory.json 2>&1
```

For Kubernetes:

```bash
SERVER_POD=$(kubectl -n infrahub get pods -l app.kubernetes.io/component=server \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n infrahub exec "$SERVER_POD" -- env \
  | grep -E '^INFRAHUB_(SECURITY|OAUTH2|OIDC)_' \
  | sed -E 's/(SECRET|TOKEN|PASSWORD)[^=]*=.*/\1=***REDACTED***/' \
                                          > bundle/category/auth-permissions/env/sso-vars.txt 2>&1

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
mkdir -p bundle/category/branch-merge/{branches,neo4j}

infrahubctl branch list --json            > bundle/category/branch-merge/branches/list.json 2>&1
infrahubctl branch report                 > bundle/category/branch-merge/branches/report.txt 2>&1 || true

# Direct Neo4j peek — bypasses the API so you see stuck branches even when the
# merge controller is wedged
docker compose exec -T database cypher-shell -u neo4j \
  -p "$INFRAHUB_DB_PASSWORD" \
  "MATCH (b:Branch) RETURN b.name, b.status, b.is_default ORDER BY b.name;" \
                                          > bundle/category/branch-merge/neo4j/branches-raw.txt 2>&1

# Prompt the user to export filtered activity CSV from the UI:
#   Open <infrahub-url>/activities, filter to "Branch", "Merge", "Delete"
#   actions, export CSV, drop file at bundle/category/branch-merge/activities.csv
cat > bundle/category/branch-merge/activities.README.txt <<'EOF'
Export the activity log filtered to Branch / Merge / Delete events from the UI
(navigate to /activities, apply the filter, click Export CSV) and save the file
at bundle/category/branch-merge/activities.csv.
EOF
```

Kubernetes is identical except the `cypher-shell`
call goes through `kubectl exec` on the database
pod (see [3.8](#38-performance) for the pattern).

## 4. Environment variable catalog

Diagnostic-relevant `INFRAHUB_*` variables. The
"Masked" column shows whether the Tier-1 redactor
strips the value before the bundle is written.

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

## 5. `/api/config` reference

`/api/config` is the server's own health and identity
endpoint. The upstream `docker-compose.yml` uses it
as the healthcheck target, so any working deployment
returns it.

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

Key fields to extract into `manifest.yml`:

| Field | Manifest target |
| ----- | --------------- |
| `version.version` | `infrahub.version` |
| `version.edition` | `infrahub.edition` |
| `version.build_sha` (if present) | `infrahub.build_sha` |

When `infrahubctl version` and `version.version`
from `/api/config` disagree, write both into the
manifest and emit a flag entry — see
[rules/manifest-template.md](rules/manifest-template.md).

## 6. `manifest.yml` schema (canonical)

The canonical schema with every required key. Mirror
this exactly when generating `bundle/manifest.yml`.

```yaml
bundle_version: "1.0"
generated_at: "2026-05-30T12:00:00Z"
skill_version: "1.2.5"               # from .claude-plugin/plugin.json
infrahub:
  version: "1.9.6"                   # from /api/config
  edition: "community"               # community | enterprise
  using_default_security_key: false  # hash compare, not value
  using_default_init_token: false
  # Optional — only present when client and server disagree
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
