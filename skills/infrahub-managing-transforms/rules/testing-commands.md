---
title: Testing Transforms
impact: LOW
tags: testing, infrahubctl, commands, rest-api
---

## Testing Transforms

**Impact:** LOW (reference)

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
# List available transforms
infrahubctl transform --list

# Run a Python transform
infrahubctl transform my_transform device=spine-01

# Render a Jinja2 transform
infrahubctl render my_jinja_transform device=spine-01

# REST API (after deployment)
# Python: GET /api/transform/python/my_transform?device=spine-01
# Jinja2: GET /api/transform/jinja2/my_transform?device=spine-01&branch=main
```

### Debugging Tips

- Test Python transforms with `infrahubctl transform` to see raw output
- Test Jinja2 templates with `infrahubctl render` to see rendered text
- Check that `query` class attribute matches the
  query `name` in `.infrahub.yml`
- Use `print()` in `transform()` during development for data inspection

Reference: [Infrahub CLI Docs](https://docs.infrahub.app)
