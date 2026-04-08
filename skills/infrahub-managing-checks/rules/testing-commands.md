---
title: Testing Checks
impact: LOW
tags: testing, infrahubctl, commands
---

## Testing Checks

Impact: LOW (reference)

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
