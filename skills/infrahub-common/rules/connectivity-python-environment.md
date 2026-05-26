---
title: Python Environment Detection for infrahubctl
impact: HIGH
tags: connectivity, infrahubctl, uv, poetry, python, environment
---

## Python Environment Detection for infrahubctl

Impact: HIGH

`infrahubctl` ships as part of the `infrahub-sdk`
package, so it only runs inside the Python
environment where that package is installed — and the
invocation prefix differs per project (`uv run`,
`poetry run`, or bare).

### Why it matters

A `command not found: infrahubctl` is almost never a
missing tool; it's the wrong shell context. The same
machine often has multiple virtualenvs and only one
of them has `infrahub-sdk` installed, so running the
command outside that env either fails outright or —
worse — picks up a stale global install and silently
talks to the wrong server version. Detect the prefix
once at the top of the workflow and reuse it; swapping
prefixes mid-session is how schemas get loaded by one
SDK version and validated by another.

### Symptoms

- `command not found: infrahubctl`
- `ModuleNotFoundError: No module named 'infrahub_sdk'`
- Unexpected Python import errors when running
  `infrahubctl` commands
- Wrong Python version or missing dependencies despite
  `infrahub-sdk` being installed

### Cause

`infrahubctl` is not on the system PATH or is being
invoked outside the project's virtual environment.
The tool needs to run within the environment where
`infrahub-sdk` is installed.

### Fix

Run the following detection sequence to determine the
correct invocation prefix. Use the first one that
succeeds:

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

If all fail, report the error to the user and
suggest:

- Checking that `infrahub-sdk` is installed in the
  project's virtual environment
- Activating the virtual environment manually
  (`source .venv/bin/activate`)
- Installing the SDK with `uv add infrahub-sdk` or
  `poetry add infrahub-sdk`

Once the working prefix is determined, reuse it for
every subsequent `infrahubctl` command in the
session. For example, if `uv run` works, stay on
`uv run infrahubctl <command>`.

### Prevention

- Detect the environment once at the start of any
  `infrahubctl` workflow — re-detecting per command
  wastes time and risks landing on a different prefix
  if one of them flakes
- Look for hints in `pyproject.toml` before trying
  commands:
  - `[tool.uv]` section present — try `uv run` first
  - `[tool.poetry]` section present — try
    `poetry run` first
- Reuse the detected prefix consistently throughout
  the session

Reference:
[Infrahub SDK](https://docs.infrahub.app)
