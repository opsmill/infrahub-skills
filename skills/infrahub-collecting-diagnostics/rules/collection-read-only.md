---
title: Collection commands must be read-only
impact: CRITICAL
tags: collection, read-only, safety
---

## Collection commands must be read-only

Impact: CRITICAL

The diagnostic skill never mutates Infrahub state.
All collection commands are read-only.

### Why it matters

A user running this skill is already in a broken
state. Running a mutating command (delete branch,
load schema, restart container) at this point can
turn a recoverable problem into a data-loss
incident. The skill must be safe to run on a
production system without coordination.

### What to do

Run only commands that observe state. Allowed verbs:
`ps`, `logs`, `inspect`, `get`, `describe`,
`list`, `show`, `report`, `export` (where export
means write-to-local-file, not write-to-server),
`stats`, `top`, `version`, `info`, `cat`, `grep`.

Forbidden verbs and flags: `delete`, `restart`,
`stop`, `down`, `rm`, `load`, `create`, `apply`,
`migrate`, `upgrade`, `restore`, `merge`, `rebase`,
`reset`, `--force`, `--yes` (without an explicit
read-only context). Never use `docker exec` to run
anything that could write to a mounted volume.

For `infrahubctl`:

| Allowed | Forbidden |
| ------- | --------- |
| `version`, `info`, `branch list`, `branch report`, `schema check`, `schema list`, `schema show`, `schema export`, `repository list`, `task list`, `telemetry export`, `dump`, `graphql --query "query{...}"` (queries only, no mutations) | `schema load`, `branch create`, `branch merge`, `branch delete`, `branch rebase`, `task delete`, `repository add`, `graphql --query "mutation{...}"` |

For `docker compose` / `kubectl` / `helm`:

| Allowed | Forbidden |
| ------- | --------- |
| `ps`, `logs`, `config`, `images`, `top`, `stats`, `get`, `describe`, `logs`, `get values`, `get manifest`, `history` | `up`, `down`, `restart`, `rm`, `delete`, `apply`, `upgrade`, `rollback`, `cp` (host->container), `exec sh -c '...write...'` |

### Compliant

```bash
docker compose ps -a --format json > bundle/state/compose-ps.json
docker compose logs --since 24h --no-color task-worker > bundle/logs/task-worker.log
infrahubctl branch list --json > bundle/state/branches.json
```

### Non-compliant

```bash
docker compose restart task-worker          # mutates
infrahubctl branch delete stuck-branch      # destroys
infrahubctl schema load schemas/*.yml       # writes to server
```

### Common mistakes

- "Restarting just to see if it helps" — not
  diagnostics, mutation.
- Using `docker compose exec sh` to "poke around"
  — the shell history may include a typo that
  mutates.
- Running `infrahubctl schema load` to "test
  whether the schema is the problem" — that's the
  user's call, not the skill's.

Reference: [infrahubctl docs](https://docs.infrahub.app/infrahubctl/infrahubctl)
