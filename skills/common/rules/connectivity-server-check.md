---
title: Server Connectivity Check
impact: HIGH
tags: connectivity, infrahubctl, server, info, offline, online
---

## Server Connectivity Check

**Impact: HIGH**

Many `infrahubctl` commands require a running Infrahub server. Always verify connectivity with `infrahubctl info` before running server-dependent commands to avoid confusing connection errors mid-workflow.

### Symptoms

- `ConnectionRefusedError` or `ConnectionError` when running `infrahubctl` commands
- Timeouts or hanging commands with no output
- `HTTPError 401 Unauthorized` or `403 Forbidden` responses
- Vague "failed to connect" messages during schema check, load, or transform execution

### Cause

The Infrahub server is not running, not reachable at the configured address, or authentication credentials are missing/invalid.

### Command Classification

| Command | Server Required | Notes |
|---------|:-:|-------|
| `infrahubctl info` | Yes | Connectivity test — run this first |
| `infrahubctl schema check` | Yes | Validates against running server's current schema |
| `infrahubctl schema load` | Yes | Loads schema into the server |
| `infrahubctl check` | Yes | Executes checks that query server data |
| `infrahubctl transform` | Yes | Runs Python transforms that query server data |
| `infrahubctl render` | Yes | Renders Jinja2 transforms that query server data |
| `infrahubctl generator` | Yes | Runs generators that query and mutate server data |
| `infrahubctl object load` | Yes | Loads data objects into the server |
| YAML linting / validation | No | Local file syntax checking |
| Python syntax check | No | `python -m py_compile file.py` |
| File structure review | No | Verify files exist and are in expected paths |

### Fix

**Step 0: Detect the Python environment**

`infrahubctl` must be invoked within the correct Python environment. Determine the right prefix before running any commands. See [connectivity-python-environment.md](connectivity-python-environment.md) for the full detection rule.

Quick reference — use the first that succeeds:

```bash
uv run infrahubctl info      # Try first if pyproject.toml has [tool.uv]
poetry run infrahubctl info   # Try next if pyproject.toml has [tool.poetry]
infrahubctl info              # Try last (direct PATH)
```

Once determined, prefix **all** `infrahubctl` commands below accordingly (e.g., `uv run infrahubctl schema check`).

**Step 1: Verify connectivity**

```bash
infrahubctl info
```

Expected output includes the server address and version:

```
Infrahub server: http://localhost:8000
Server version: x.y.z
```

**Step 2: Check environment variables**

```bash
# Server address (defaults to http://localhost:8000 if not set)
echo $INFRAHUB_ADDRESS

# API token for authentication
echo $INFRAHUB_API_TOKEN
```

Set them if missing:

```bash
export INFRAHUB_ADDRESS="http://localhost:8000"
export INFRAHUB_API_TOKEN="your-api-token"
```

**Step 3: Troubleshoot connection failures**

1. **Is the server running?** Check with `docker ps` or the relevant process manager
2. **Is the address correct?** Verify `INFRAHUB_ADDRESS` matches the actual server URL
3. **Is the token valid?** Regenerate the API token from the Infrahub UI if needed
4. **Is the network reachable?** Test with `curl -s $INFRAHUB_ADDRESS/api/health`

### Prevention

- Always run `infrahubctl info` as the first step before any server-dependent workflow
- For offline work (no server available), limit to local validation:
  - YAML linting and structure checks
  - Python syntax verification (`python -m py_compile`)
  - File and directory structure review against `.infrahub.yml`
  - Schema YAML format checks (correct keys, naming conventions)
- Set `INFRAHUB_ADDRESS` and `INFRAHUB_API_TOKEN` in your shell profile or `.env` file for consistent configuration

Reference: [Infrahub CLI Docs](https://docs.infrahub.app)
