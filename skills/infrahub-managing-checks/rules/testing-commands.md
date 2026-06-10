---
title: Testing Checks
impact: LOW
tags: testing, infrahubctl, commands
---

## Testing Checks

Impact: LOW (reference)

Run checks locally with `infrahubctl check` against a
feature branch before opening a proposed change.

### Why it matters

The proposed-change pipeline is the wrong place to
discover that a check raises `AttributeError` or
fetches an empty payload — every failed iteration
costs a branch push and a pipeline run, and the
traceback shows up to reviewers rather than to the
author. Running `infrahubctl check` locally exercises
the same SDK path the pipeline uses, so a check that
passes locally on a representative branch will behave
the same way in the pipeline, and one that explodes
locally never reaches a reviewer.

### Prerequisites

All commands below require a running Infrahub server.
Verify connectivity first:

```bash
infrahubctl info
```

See
[Server Connectivity Check](../../infrahub-common/rules/connectivity-server-check.md)
for troubleshooting.

### Commands

```bash
# List available checks
infrahubctl check --list

# Run a specific check
infrahubctl check my_check_name

# Run against a specific branch
infrahubctl check my_check_name \
    --branch=feature-branch
```

### Debugging Tips

- Check logs for `ERROR` entries to see what failed
- Use `log_info()` liberally during development to
  trace data flow
- Test against a branch first before running on main
- Global checks run on every proposed change -- keep
  them efficient

Reference:
[Infrahub CLI Docs](https://docs.infrahub.app)
