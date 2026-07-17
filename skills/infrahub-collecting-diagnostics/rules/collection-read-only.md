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

On Kubernetes, `infrahub-collect` only needs read
access to `pods/log` and `pods/exec` — no write or
scale permissions. Never run `kubectl delete`,
`kubectl scale`, `docker compose down`, `docker
compose restart`, or any command that mutates cluster
or container state.

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
- Requesting broader Kubernetes RBAC than
  `pods/log` + `pods/exec` read access "just in
  case" — the tool never needs more than that.
- Reaching for `docker compose exec`/`kubectl exec`
  to "poke around" instead of trusting
  `infrahub-collect create` to gather what's needed.

Reference: [Install infrahub-collect](https://docs.infrahub.app/backup/guides/install-collect)
