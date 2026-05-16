# Infrahub Ecosystem Repo Registry

The 11 repositories where Infrahub-ecosystem issues
live. Use this registry in step 3 of the workflow to
route an incoming report to the right repo.

When in doubt, default to `opsmill/infrahub`. The
main repo can re-route an issue to a sub-repo more
easily than the reverse.

## Routing precedence

1. Strong local cue + matching user description → use
   the matched repo.
2. Strong local cue, but user describes a different
   product → use the product the user describes.
3. Weak or no local cue → ask the user one
   clarifying question, then default to
   `opsmill/infrahub` if still ambiguous.

## Registry

### `opsmill/infrahub` — the platform (default fallback)

Graph-based infrastructure data management platform
with built-in version control, CI workflows, peer
review, and API access. The core product that
everything else integrates with.

**Detection cues**:

- `infrahub.toml` in repo root
- `docker-compose*.yml` referencing `infrahub-server`,
  `infrahub-task-worker`, or `infrahub-task-manager`
- Schema YAML with `version: "1.0"` plus `nodes:` or
  `generics:`
- `.infrahub.yml` (this also matches several other
  repos — not exclusive)

**Issue templates**: `bug_report.yml`,
`feature_request.yml`, `task.yml`

**URL**: <https://github.com/opsmill/infrahub>

---

### `opsmill/infrahub-sdk-python` — the Python SDK

Python SDK for interacting with Infrahub
programmatically. Used by checks, generators,
transforms, and any custom Python code talking to an
Infrahub server.

**Detection cues**:

- `infrahub-sdk` in `pyproject.toml` dependencies or
  `requirements*.txt`
- `import infrahub_sdk` or `from infrahub_sdk import
  ...` in Python files
- Error messages mentioning `InfrahubClient`,
  `InfrahubClientSync`, or `infrahub_sdk.*` modules

**Issue templates**: `bug_report.yml`,
`feature_request.yml`, `task.yml`

**URL**: <https://github.com/opsmill/infrahub-sdk-python>

---

### `opsmill/infrahub-vscode` — the VS Code extension

Visual Studio Code extension that enhances the
Infrahub development experience (schema validation,
syntax highlighting, etc.).

**Detection cues**:

- Filesystem cues are unreliable for this one. Rely
  on the user describing VS Code, the extension UI,
  or editor-specific behavior.

**Issue templates**: none — use generic
`templates/bug.md` / `templates/feature.md`.

**URL**: <https://github.com/opsmill/infrahub-vscode>

---

### `opsmill/infrahub-ansible` — the Ansible Collection

Ansible Collection for managing Infrahub resources
from playbooks. Provides modules and inventory plugins
for the `opsmill.infrahub` namespace.

**Detection cues**:

- `ansible_collections/opsmill/infrahub/` directory
- `galaxy.yml` referencing `opsmill.infrahub`
- Playbooks using `opsmill.infrahub.*` modules
- Inventory files with `plugin: opsmill.infrahub.inventory`

**Issue templates**: `bug_report.yml`,
`feature_request.yml`, `documentation_change.yml`,
`housekeeping.yml`

**URL**: <https://github.com/opsmill/infrahub-ansible>

---

### `opsmill/nornir-infrahub` — the Nornir plugin

Nornir inventory plugin for sourcing devices from
Infrahub. Used in Python automation workflows that
combine Infrahub with Nornir/NAPALM/Netmiko.

**Detection cues**:

- `nornir-infrahub` in `pyproject.toml` dependencies
- `import nornir_infrahub` or
  `from nornir_infrahub.plugins.inventory import
  InfrahubInventory`
- Nornir config files referencing the plugin

**Issue templates**: `bug_report.yml`,
`feature_request.yml`, `task.yml`

**URL**: <https://github.com/opsmill/nornir-infrahub>

---

### `opsmill/infrahub-helm` — the Helm chart

Helm charts for deploying Infrahub on Kubernetes.

**Detection cues**:

- `Chart.yaml` with `name: infrahub` or referencing
  the opsmill chart repo
- `values.yaml` with Infrahub-specific keys
  (`infrahub.server.*`, `infrahub.cache.*`)
- Kubernetes manifests generated from the chart

**Issue templates**: none — use generic templates.

**URL**: <https://github.com/opsmill/infrahub-helm>

---

### `opsmill/infrahub-mcp` — the MCP server

MCP (Model Context Protocol) server exposing Infrahub
to AI coding agents. Used by Claude Code and other
MCP clients to query live Infrahub data.

**Detection cues**:

- MCP client config (`.mcp.json`, Claude Desktop
  config, etc.) with an `infrahub-mcp` entry
- `infrahub-mcp` pip-installed
- User mentions querying Infrahub through their AI
  agent or "the Infrahub MCP"

**Issue templates**: none — use generic templates.

**URL**: <https://github.com/opsmill/infrahub-mcp>

---

### `opsmill/schema-library` — the schema library

Curated collection of reusable Infrahub schemas
(DCIM, IPAM, etc.) that users can drop into their
projects as a starting point.

**Detection cues**:

- The user is reporting a problem with a specific
  schema they got from the library
- Local layout mirrors the upstream `schemas/`
  directory structure
- Schema files that match published library schemas
  (e.g., generic `DcimDevice` schemas)

**Issue templates**: none — use generic templates.

**URL**: <https://github.com/opsmill/schema-library>

---

### `opsmill/infrahub-backup` — the backup CLI

CLI tool for backing up and restoring Infrahub data
(database snapshots, etc.).

**Detection cues**:

- `infrahub-backup` invocations in shell scripts or
  cron entries
- `pip show infrahub-backup` succeeds
- User mentions backup/restore workflows

**Issue templates**: none — use generic templates.

**URL**: <https://github.com/opsmill/infrahub-backup>

---

### `opsmill/infrahub-sync` — the sync tool

Python package + Typer CLI for syncing data between
Infrahub and other sources of truth (Netbox,
Nautobot, etc.).

**Detection cues**:

- `infrahub-sync` in `pyproject.toml` dependencies
- `sync.yml` configuration files
- The user is reporting bidirectional sync issues
  between Infrahub and Netbox/Nautobot

**Issue templates**: none — use generic templates.

**URL**: <https://github.com/opsmill/infrahub-sync>

---

### `opsmill/infrahub-skills` — this plugin

The Claude Code plugin that contains these skills
themselves (schema, objects, checks, etc.).

**Detection cues**:

- `.claude-plugin/plugin.json` with `"name":
  "infrahub"`
- `skills/infrahub-*/SKILL.md` files present
- User reporting a problem with skill behavior
  (e.g., "the managing-schemas skill generates wrong
  output")

**Issue templates**: none — use generic templates.

**URL**: <https://github.com/opsmill/infrahub-skills>

## Template availability summary

| Repo | bug | feature | other |
| ---- | --- | ------- | ----- |
| `opsmill/infrahub` | yes | yes | task |
| `opsmill/infrahub-sdk-python` | yes | yes | task |
| `opsmill/infrahub-ansible` | yes | yes | doc, housekeeping |
| `opsmill/nornir-infrahub` | yes | yes | task |
| `opsmill/infrahub-vscode` | — | — | — |
| `opsmill/infrahub-helm` | — | — | — |
| `opsmill/infrahub-mcp` | — | — | — |
| `opsmill/schema-library` | — | — | — |
| `opsmill/infrahub-backup` | — | — | — |
| `opsmill/infrahub-sync` | — | — | — |
| `opsmill/infrahub-skills` | — | — | — |

For repos with templates, fetch the YAML form via
`gh api` and follow its field order. For the rest,
fall back to the generic templates in this skill.
