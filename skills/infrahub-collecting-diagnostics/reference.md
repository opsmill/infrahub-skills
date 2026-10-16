# Reference — `infrahub-collect`

Command and flag reference for the `infrahub-collect`
binary. The workflow in [SKILL.md](SKILL.md) links
here for the exact syntax at each step.

## Install

Download the binary for the user's OS/architecture,
make it executable, and optionally move it onto
`PATH`:

```bash
curl https://infrahub.opsmill.io/ops/$(uname -s)/$(uname -m)/infrahub-collect -o infrahub-collect
chmod +x infrahub-collect
sudo mv infrahub-collect /usr/local/bin/   # optional
```

`$(uname -s)`/`$(uname -m)` resolve to one of:

| OS | Arch | URL |
| -- | ---- | --- |
| Linux | x86_64 | `https://infrahub.opsmill.io/ops/Linux/x86_64/infrahub-collect` |
| Linux | aarch64 | `https://infrahub.opsmill.io/ops/Linux/aarch64/infrahub-collect` |
| Darwin | x86_64 | `https://infrahub.opsmill.io/ops/Darwin/x86_64/infrahub-collect` |
| Darwin | arm64 | `https://infrahub.opsmill.io/ops/Darwin/arm64/infrahub-collect` |

Unsupported platform, or airgapped with no way to
fetch the binary directly: build from source (needs
Go 1.25+).

**Verify:**

```bash
infrahub-collect version
infrahub-collect --help
```

See [rules/install-and-verify.md](rules/install-and-verify.md).

## Environment detection

```bash
infrahub-collect environment detect
infrahub-collect environment list
```

`detect` identifies the deployment topology (Docker
Compose or Kubernetes) automatically using existing
Docker/kubectl access — no Infrahub API token is
needed. `list` shows candidates when detection is
ambiguous.

Disambiguate with:

- `--project=<name>` — Compose project name; must
  contain `infrahub` (auto-detection matches on this
  substring).
- `--k8s-namespace=<ns>` — Kubernetes namespace;
  auto-detection otherwise looks for pods labeled
  `app.kubernetes.io/name=infrahub`.

On Kubernetes, only read access to `pods/log` and
`pods/exec` is required.

See [rules/deployment-detection.md](rules/deployment-detection.md).

## `create` flags

```bash
infrahub-collect create [flags]
```

| Flag | Effect |
| ---- | ------ |
| `--project=<name>` | Target a specific Compose project (name must contain `infrahub`) |
| `--k8s-namespace=<ns>` | Target a specific Kubernetes namespace |
| `--output-dir=<path>` | Where the bundle is written (default `./infrahub_bundles`) |
| `--include-queries` | Include DB query logs. Off by default — may contain customer data |
| `--benchmark` | Run a host resource benchmark. Pulls an OpsMill image; skipped with a warning if unavailable (e.g. airgapped) |
| `--include-backup` | Include a backup, for support-requested reproduction |
| *(log volume)* | A flag exists to adjust the log volume limit collected per service — check `infrahub-collect create --help` for the current flag name/default rather than assuming one |

Match flags to the reported symptom rather than adding
all of them by default — see
[rules/create-flags.md](rules/create-flags.md).

**Environment variables** (alternatives to flags):

| Variable | Equivalent to |
| -------- | ------------- |
| `INFRAHUB_PROJECT` | `--project` |
| `INFRAHUB_OUTPUT_DIR` | `--output-dir` |

`create` exits `0` even on a partial collection —
failures are recorded in the manifest, not raised as
errors. See
[rules/collection-read-only.md](rules/collection-read-only.md).

## Bundle layout

```text
bundle/
├── bundle_information.json   # manifest: what was collected, what failed
├── logs/
│   └── <service>/            # one file per replica
│       └── *.previous.log    # present after container restarts
├── database/
├── message-queue/
├── cache/
├── task-worker/
├── task-manager/
├── server/
└── metrics/
```

`bundle_information.json` is the first thing an expert
opens — read it to see what succeeded and what a
degraded deployment prevented from being collected.
See [rules/bundle-layout.md](rules/bundle-layout.md).

## Troubleshoot collection

**No deployment detected.**
Run `infrahub-collect environment list` and
`docker compose ls` to see what's actually running.
For Compose, the project name must contain
`infrahub`, or pass `--project=<name>` explicitly. For
Kubernetes, the target namespace's pods need the label
`app.kubernetes.io/name=infrahub`, or pass
`--k8s-namespace=<ns>`.

**Permission denied on Kubernetes.**
`infrahub-collect` needs read access to `pods/log` and
`pods/exec` in the target namespace. Ask the user (or
their platform team) to grant that RBAC rather than
escalating to broader access.

**`docker`/`kubectl` not found.**
`infrahub-collect` shells out to whichever CLI matches
the detected topology. Install/put on `PATH` the CLI
for the deployment in question before retrying.

**Individual collectors failed.**
Expected on a degraded deployment (e.g. a crashed
service with no logs to read). `create` still exits
`0` and records the failure in
`bundle_information.json`. Send the partial bundle
as-is — don't try to patch the gap by hand.

## Docs

- [Install infrahub-collect](https://docs.infrahub.app/backup/collect/install)
- [Collect a diagnostic bundle](https://docs.infrahub.app/backup/collect/create)
