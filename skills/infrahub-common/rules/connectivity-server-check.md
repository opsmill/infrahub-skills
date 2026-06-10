---
title: Server Connectivity Check
impact: HIGH
tags: connectivity, infrahubctl, server, info, offline, online
---

## Server Connectivity Check

Impact: HIGH

Most `infrahubctl` commands talk to a live server, so
running `infrahubctl info` first turns "is the server
reachable?" into a one-line yes/no instead of a
confusing failure ten steps into a workflow.

### Why it matters

`schema check`, `object load`, `generator`,
`transform`, and `render` all fail differently when
the server is down or misconfigured — sometimes with
a clean `ConnectionRefusedError`, sometimes with a
401 that looks like a permission bug, sometimes with
a hang. Each surfaces deep inside the command's
output, after partial work may have already been
attempted. A 2-second `infrahubctl info` up front
gives a clean diagnosis (SDK loaded, address set,
token valid) before any state-changing command runs,
which keeps recovery cheap.

### Symptoms

- `ConnectionRefusedError` or `ConnectionError` when
  running `infrahubctl` commands
- Timeouts or hanging commands with no output
- `HTTPError 401 Unauthorized` or `403 Forbidden`
  responses
- Vague "failed to connect" messages during schema
  check, load, or transform execution

### Cause

The Infrahub server is not running, not reachable at
the configured address, or authentication credentials
are missing/invalid.

### Command Classification

| Command | Server | Notes |
| ------- | :----: | ----- |
| `infrahubctl info` | Yes | Connectivity test -- run first |
| `infrahubctl schema check` | Yes | Validates against server schema |
| `infrahubctl schema load` | Yes | Loads schema into server |
| `infrahubctl check` | Yes | Executes checks that query data |
| `infrahubctl transform` | Yes | Runs Python transforms |
| `infrahubctl render` | Yes | Renders Jinja2 transforms |
| `infrahubctl generator` | Yes | Runs generators |
| `infrahubctl object load` | Yes | Loads data objects |
| YAML linting / validation | No | Local file syntax checking |
| Python syntax check | No | `python -m py_compile file.py` |
| File structure review | No | Verify files exist at paths |

### Fix

#### Step 0: Detect the Python environment

`infrahubctl` runs inside the project's Python
environment — get the right prefix before issuing
any commands. See
[connectivity-python-environment.md](connectivity-python-environment.md)
for the full detection rule.

Quick reference -- use the first that succeeds:

```bash
uv run infrahubctl info      # Try first if [tool.uv]
poetry run infrahubctl info   # Try if [tool.poetry]
infrahubctl info              # Try last (direct PATH)
```

Once determined, prefix every `infrahubctl` command
below the same way (e.g.,
`uv run infrahubctl schema check`).

#### Step 1: Verify connectivity

```bash
infrahubctl info
```

Expected output includes the server address and
version:

```text
Infrahub server: http://localhost:8000
Server version: x.y.z
```

#### Step 2: Check environment variables

```bash
# Server address (defaults to localhost:8000)
echo $INFRAHUB_ADDRESS

# API token for authentication
echo $INFRAHUB_API_TOKEN
```

Set them if missing:

```bash
export INFRAHUB_ADDRESS="http://localhost:8000"
export INFRAHUB_API_TOKEN="your-api-token"
```

#### Step 3: Troubleshoot connection failures

1. **Is the server running?** Check with `docker ps`
   or the relevant process manager
2. **Is the address correct?** Verify
   `INFRAHUB_ADDRESS` matches the actual server URL
3. **Is the token valid?** Regenerate the API token
   from the Infrahub UI if needed
4. **Is the network reachable?** Test with
   `curl -s $INFRAHUB_ADDRESS/api/health`

### Prevention

- Run `infrahubctl info` as the first step of any
  server-dependent workflow — it's the cheapest
  signal that the rest of the run has a chance of
  succeeding
- For offline work (no server available), limit to
  local validation:
  - YAML linting and structure checks
  - Python syntax verification (`python -m py_compile`)
  - File and directory structure review against
    `.infrahub.yml`
  - Schema YAML format checks (correct keys, naming
    conventions)
- Set `INFRAHUB_ADDRESS` and `INFRAHUB_API_TOKEN` in
  your shell profile or `.env` file for consistent
  config

Reference:
[Infrahub CLI Docs](https://docs.infrahub.app)
