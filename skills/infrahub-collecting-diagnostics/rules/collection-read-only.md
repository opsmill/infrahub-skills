---
title: Collection commands must be read-only
impact: CRITICAL
tags: collection, read-only, safety
---

## Collection commands must be read-only

Impact: CRITICAL

The diagnostic skill never mutates Infrahub state.
`infrahub-collect` itself is read-only by design, and
the skill must not add any command around it that
isn't.

One change is part of the plan but not run by the
agent: for a slowness the operator can reproduce, a
super admin raises the trace sampling ratio for a
limited time and removes it after the bundle (`PUT`
and `DELETE` on
`/api/troubleshooting/trace-sample-ratio`). The
operator runs both calls. See
[create-traces.md](create-traces.md).

### Why it matters

A user running this skill is already in a broken
state. Running a mutating command (restarting a
container, deleting a pod, scaling a deployment) at
this point can turn a recoverable problem into a
data-loss incident. The skill must be safe to run on
a production system without coordination.

### What to do

Run only `infrahub-collect` subcommands
(`version`, `environment detect`, `environment list`,
`create`) plus read-only inspection commands
(`docker compose ps`, `docker compose logs`,
`kubectl get pods`, `kubectl logs`) if the user needs
extra context beyond what the bundle captured.

On Kubernetes, `infrahub-collect` needs read access
to `pods/log` and `pods/exec`, and no write or scale
permissions. `--include-traces` also needs `create`
on `pods/portforward` and `list` on `services`, to
reach the Tempo pod (see
[create-traces.md](create-traces.md)). Never run
`kubectl delete`, `kubectl scale`, `docker compose
down`, `docker compose restart`, or any command that
mutates cluster or container state.

### Compliant

```bash
infrahub-collect version
infrahub-collect environment detect
infrahub-collect create --benchmark
```

### Non-compliant

```bash
docker compose restart task-worker    # mutates
kubectl delete pod infrahub-server-0  # destroys
kubectl scale deployment task-worker --replicas=0  # mutates
```

### Common mistakes

- "Restarting just to see if it helps" — not
  diagnostics, mutation.
- Requesting broader Kubernetes RBAC than the
  collection needs "just in case": `pods/log` and
  `pods/exec`, plus `pods/portforward` (`create`) and
  `services` (`list`) only with `--include-traces`.
- Reaching for `docker compose exec`/`kubectl exec`
  to "poke around" instead of trusting
  `infrahub-collect create` to gather what's needed.

Reference: [Install infrahub-collect](https://docs.infrahub.app/backup/collect/install)
