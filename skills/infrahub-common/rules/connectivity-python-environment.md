---
title: Python Environment Detection for infrahubctl
impact: HIGH
tags: connectivity, infrahubctl, uv, poetry, python, environment
---

## Python Environment Detection for infrahubctl

Impact: HIGH

`infrahubctl` is a Python CLI tool from the `infrahub-sdk`
package. It must be invoked within the correct Python
environment. Different projects use different package
managers (`uv`, `poetry`, or direct installation), so the
invocation prefix varies.

### Symptoms

- `command not found: infrahubctl`
- `ModuleNotFoundError: No module named 'infrahub_sdk'`
- Unexpected Python import errors when running
  `infrahubctl` commands
- Wrong Python version or missing dependencies despite
  `infrahub-sdk` being installed

### Cause

`infrahubctl` is not on the system PATH or is being
invoked outside the project's virtual environment. The
tool needs to run within the environment where
`infrahub-sdk` is installed.

### Fix

Run the following detection sequence to determine the
correct invocation prefix. Use the first one that succeeds:

Try `uv` first:

```bash
uv run infrahubctl info
```

Then try `poetry`:

```bash
poetry run infrahubctl info
```

Then try direct invocation:

```bash
infrahubctl info
```

If all fail, report the error to the user and suggest:

- Checking that `infrahub-sdk` is installed in the
  project's virtual environment
- Activating the virtual environment manually
  (`source .venv/bin/activate`)
- Installing the SDK with `uv add infrahub-sdk` or
  `poetry add infrahub-sdk`

Once the working prefix is determined, use it for **all**
subsequent `infrahubctl` commands in the session. For
example, if `uv run` works, always use
`uv run infrahubctl <command>`.

### Prevention

- Detect the environment once at the start of any
  `infrahubctl` workflow -- do not re-detect for each
  command
- Look for hints in `pyproject.toml` before trying
  commands:
  - `[tool.uv]` section present -- try `uv run` first
  - `[tool.poetry]` section present -- try `poetry run`
    first
- Reuse the detected prefix consistently throughout
  the session

Reference:
[Infrahub SDK](https://docs.infrahub.app)
