---
title: Defer environment detection to the tool
impact: HIGH
tags: deployment, detection, environment
---

## Defer environment detection to the tool

Impact: HIGH

`infrahub-collect` detects the deployment topology
itself. Don't hand-roll `docker compose ps` /
`kubectl get pods` probing — run the tool's own
detection commands and let them decide.

### Why it matters

Hand-rolled topology detection duplicates logic that
already lives in the tool and drifts out of sync with
it — a new deployment mode the tool learns to detect
would still be invisible to a hand-rolled probe. It
also risks guessing wrong on ambiguous hosts (multiple
Compose projects, non-default K8s namespaces) in ways
the tool's own flags are built to disambiguate.

### What to do

Run detection first:

```bash
infrahub-collect environment detect
```

If the result is ambiguous — multiple Compose
projects on the host, or a non-default Kubernetes
namespace — list the candidates and disambiguate
explicitly:

```bash
infrahub-collect environment list
```

- `--project=<name>` — the Compose project name must
  contain `infrahub`.
- `--k8s-namespace=<ns>` — the namespace whose pods
  carry the label `app.kubernetes.io/name=infrahub`.

No Infrahub API token is required for any of this —
the tool reuses the user's existing Docker or
`kubectl` access. On Kubernetes it only needs
read access to `pods/log` and `pods/exec`.

### Compliant

```bash
infrahub-collect environment detect
# ambiguous — multiple Compose projects found
infrahub-collect environment list
infrahub-collect create --project=infrahub-prod
```

### Non-compliant

```bash
docker compose ps
kubectl -n infrahub get pods
# hand-rolled detection instead of using the tool
```

### Common mistakes

- Falling back to manual `docker compose ps` /
  `kubectl get pods` probing instead of
  `infrahub-collect environment detect`/`list`.
- Assuming the default namespace or Compose project
  without running `environment list` when detection
  reports ambiguity.
- Asking the user for an Infrahub API token — the
  tool never needs one; it only needs the
  Docker/kubectl access already on the host.

Reference: [Install infrahub-collect](https://docs.infrahub.app/backup/guides/install-collect)
