---
title: Detect deployment topology before any collection
impact: HIGH
tags: deployment, topology, detection
---

## Detect deployment topology before any collection

Impact: HIGH

Every later command shape (how to list services, how
to fetch logs, how to read config) depends on the
deployment topology. Detect it first by running cheap
read-only probes in a fixed order, and only fall back
to asking the user when every probe has failed.

### Why it matters

The same Infrahub instance is addressed very
differently from Compose, Kubernetes, and local-dev.
A `docker compose logs` command silently produces an
empty result when Infrahub is actually running in
Kubernetes on a remote cluster — the collector then
ships an empty `logs/` directory and the expert has
nothing to work with. Detect the topology
deterministically before any command shape is chosen.

### What to do

Run probes in this order, stopping at the first
success:

1. `docker compose ps` — exits 0 with non-empty
   output → **Docker Compose**.
2. `kubectl -n infrahub get pods` — exits 0 with
   non-empty output → **Kubernetes**.
3. `tasks/demo.py` exists and `invoke demo.status`
   exits 0 → **local dev**.
4. **Manual fallback** — none of the above
   succeeded; ask the user which topology is in
   use.

Record the detected value in `manifest.yml` under
`deployment.topology` (one of `docker-compose`,
`kubernetes`, `local-dev`, `manual`).

Service names are stable across Compose and Helm.
For every later step, address each canonical service
using the per-topology pattern below:

| Canonical service | Docker Compose container | Kubernetes label selector |
|---|---|---|
| `infrahub-server` | `infrahub-server-*` | `app.kubernetes.io/component=infrahub-server` |
| `task-worker` | `infrahub-task-worker-*` | `app.kubernetes.io/component=task-worker` |
| `database` | `database-*` | `app.kubernetes.io/component=database` |
| `cache` | `cache-*` | `app.kubernetes.io/component=cache` |
| `message-queue` | `message-queue-*` | `app.kubernetes.io/component=message-queue` |
| `task-manager` | `task-manager-*` | `app.kubernetes.io/component=task-manager` |
| `task-manager-db` | `task-manager-db-*` | `app.kubernetes.io/component=task-manager-db` |

### Compliant

```bash
# Try probes in order
if docker compose ps -q | grep -q .; then
  TOPOLOGY=docker-compose
elif kubectl -n infrahub get pods --no-headers 2>/dev/null | grep -q .; then
  TOPOLOGY=kubernetes
elif [ -f tasks/demo.py ] && invoke demo.status >/dev/null 2>&1; then
  TOPOLOGY=local-dev
else
  TOPOLOGY=manual    # ask the user
fi
```

```bash
# Then address task-worker per topology
# Compose:
docker ps --filter name=task-worker --format '{{.Names}}'
# Kubernetes:
kubectl -n infrahub get pods -l app.kubernetes.io/component=task-worker -o name
```

### Non-compliant

```bash
# Assumes Compose because docker is installed locally,
# even though Infrahub is running in a remote K8s cluster.
docker compose logs task-worker > bundle/baseline/logs/task-worker.log
# Result: empty file, no error surfaced, expert has nothing
```

### Common mistakes

- Assuming Docker Compose because the dev machine
  has `docker` installed. The user may be running
  Infrahub in K8s on a remote cluster reached via
  `kubectl`. Run the probes; do not infer from
  the local toolchain.
- Skipping the probe step and asking the user
  immediately. The probe is cheaper than a
  question and removes a chance for the user to
  guess wrong.
- Hardcoding service names like `infrahub_server`
  (underscore) or `infra-server` (truncated). The
  canonical names in the service-name map are the
  contract; anything else breaks the per-category
  collection commands later.

Reference: [opsmill/infrahub docker-compose.yml](https://github.com/opsmill/infrahub/blob/main/docker-compose.yml)
