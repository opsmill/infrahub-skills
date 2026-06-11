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

For `infrahubctl` — this is the **only** tool used to
probe instance state, see
[infrahubctl-only-for-instance.md](infrahubctl-only-for-instance.md):

| Allowed | Forbidden |
| ------- | --------- |
| `version`, `info`, `branch list` (text output only — no `--json`, the flag does not exist), `branch report <BRANCH_NAME>`, `schema check`, `schema list`, `schema show`, `schema export`, `repository list`, `task list` (with `--json`, `--include-logs`, `-s <STATE>` filters), `telemetry export`, `dump`, `run`, `graphql export-schema`, `graphql generate-return-types` | `schema load`, `branch create`, `branch merge`, `branch delete`, `branch rebase`, `task delete`, `repository add`, any GraphQL mutation, and anything `infrahubctl` doesn't actually expose (e.g., ad-hoc query subcommand — it doesn't exist) |

For `docker compose` / `kubectl` / `helm` —
**deployment-layer** inspection, not instance probes:

| Allowed | Forbidden |
| ------- | --------- |
| `ps`, `logs`, `config`, `images`, `top`, `stats`, `inspect`, `network ls`, `network inspect`, `get`, `describe`, `events`, `get values`, `get manifest`, `history` | `up`, `down`, `restart`, `rm`, `delete`, `apply`, `upgrade`, `rollback`, `cp` (host->container), `exec sh -c '...write...'` |

### Anything else against the instance — forbidden

This rule's read-only/no-mutation coverage is one
half. The other half is the source of the probe.
Even read-only, the following are out:

- `curl http://.../api/...` — speculative HTTP probe.
- `curl -sX POST http://.../graphql -d '...'` —
  speculative GraphQL probe.
- `docker compose exec <stack-container> cypher-shell` —
  direct Neo4j peek.
- `docker compose exec <stack-container> psql` —
  direct Prefect Postgres peek.
- `docker compose exec <stack-container> rabbitmqctl` —
  direct RabbitMQ peek.
- `docker compose exec <stack-container> neo4j-admin` —
  bundled DB diagnostic tool.
- `docker compose exec <stack-container> env|printenv` —
  env probe inside an Infrahub-stack container.
- `kubectl exec` equivalents of any of the above.

All of these are version-coupled to internal
implementation details and break silently across
Infrahub releases. See
[infrahubctl-only-for-instance.md](infrahubctl-only-for-instance.md).

### Compliant

```bash
docker compose ps -a --format json > bundle/state/compose-ps.json
docker compose logs --since 24h --no-color task-worker > bundle/logs/task-worker.log
infrahubctl branch list > bundle/state/branches.txt
infrahubctl repository list > bundle/state/repositories.txt
infrahubctl task list --json --limit 50 > bundle/state/recent-tasks.json
```

### Non-compliant

```bash
docker compose restart task-worker          # mutates
infrahubctl branch delete stuck-branch      # destroys
infrahubctl schema load schemas/*.yml       # writes to server
infrahubctl branch list --json              # --json doesn't exist on this subcommand
curl -sX POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"query { Branch { name status }}"}' \
  > branches.json                           # forbidden source
docker compose exec -T database cypher-shell -u neo4j -p "$X" \
  "MATCH (b:Branch) RETURN b.name, b.status"  # forbidden source
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
- Adding `--json` to `infrahubctl branch list`
  because other subcommands accept it — this one
  does not. Use the text output, parse with `awk`
  if you need columns.

Reference: [infrahubctl docs](https://docs.infrahub.app/infrahubctl/infrahubctl)
