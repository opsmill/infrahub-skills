---
title: Always collect from every task-worker replica
impact: CRITICAL
tags: multi-replica, coverage, race-conditions
---

## Always collect from every task-worker replica

Impact: CRITICAL

Recent Infrahub bugs (issues
[#9036](https://github.com/opsmill/infrahub/issues/9036),
[#9293](https://github.com/opsmill/infrahub/issues/9293),
[#9349](https://github.com/opsmill/infrahub/issues/9349))
are multi-worker race conditions. Collecting only one
replica's logs hides the root cause.

### Why it matters

When two workers race to write to the same git
directory, the failing worker's log shows
`CommitNotFoundError` while the winning worker's log
shows the same commit succeeding. Without both logs
in the bundle, the expert cannot tell whether the
problem is a race, a configuration error, or a
single-worker bug.

### What to do

Enumerate replicas first. For Compose:

```bash
docker ps --filter name=task-worker --format '{{.Names}}'
```

For Kubernetes:

```bash
kubectl -n infrahub get pods -l app.kubernetes.io/component=task-worker -o name
```

Then iterate, writing one log file per replica into
`bundle/baseline/logs/`:

```bash
for c in $(docker ps --filter name=task-worker --format '{{.Names}}'); do
  docker logs --since 24h "$c" > "bundle/baseline/logs/${c}.log" 2>&1
done
```

Record the replica count in `manifest.yml` under
`deployment.worker_replicas`.

### Compliant

```text
bundle/baseline/logs/
├── infrahub-task-worker-1.log
├── infrahub-task-worker-2.log
└── infrahub-task-worker-3.log
```

### Non-compliant

```text
bundle/baseline/logs/
└── task-worker.log    # only one replica sampled
```

### Common mistakes

- `docker compose logs task-worker` interleaves
  all replicas into one stream — readable for
  humans, but loses the per-replica boundary that
  the expert needs. Use per-container `docker
  logs` instead.
- Forgetting that the API server itself can also
  have multiple replicas in Kubernetes. Apply the
  same per-replica collection to `infrahub-server`
  in K8s.

Reference: [Issue #9036](https://github.com/opsmill/infrahub/issues/9036)
