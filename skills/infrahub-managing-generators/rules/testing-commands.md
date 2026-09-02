---
title: Testing Generators
impact: LOW
tags: testing, infrahubctl, commands
---

## Testing Generators

Impact: LOW (reference)

`infrahubctl generator` runs a generator locally
against a real server, bypassing the dispatcher but
preserving the tracking context.

### Why it matters

Local runs are the only way to iterate on a
generator without round-tripping through proposed
changes; the same tracking behavior applies, so a
half-finished local run still deletes objects the
previous full run created. Passing the target's key
attribute on the command line (e.g.,
`name=dc-topology-1`) is what supplies the GraphQL
variable defined in `parameters` — omitting it makes
the query return zero rows and the generator looks
like it ran cleanly while doing nothing.

### Prerequisites

All commands below require a running Infrahub server,
with one exception: `infrahubctl generator --list` reads
the local `.infrahub.yml` and never contacts the server.
Verify connectivity first:

```bash
infrahubctl info
```

See [Server Connectivity Check](../../infrahub-common/rules/connectivity-server-check.md)
for troubleshooting.

### Commands

```bash
# List the generators declared in .infrahub.yml.
# Local only: this never contacts the server, so it says
# nothing about whether the config loaded or the target
# group resolved.
infrahubctl generator --list

# Run a generator locally
infrahubctl generator create_dc \
  --branch=my-branch name=dc-topology-1

# Generators also run automatically:
# - When target objects change in proposed changes
# - After branch merges (if execute_after_merge=True)
```

### Debugging Tips

- Use `self.logger` inside `generate()` for operation
  tracking
- Test with a small design first (1-2 elements) before
  scaling
- Check that target `CoreGeneratorGroup` exists and has
  members
- Verify query variables match `parameters` mapping in
  `.infrahub.yml`

Reference:
[Infrahub CLI Docs](https://docs.infrahub.app)
