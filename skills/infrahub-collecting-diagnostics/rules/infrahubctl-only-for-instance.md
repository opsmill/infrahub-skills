---
title: Use infrahubctl exclusively for instance state
impact: CRITICAL
tags: collection, contract, stability
---

## Use `infrahubctl` exclusively for instance state

Impact: CRITICAL

When the skill probes the running Infrahub instance
for state — branches, repositories, schemas, tasks,
telemetry — it uses `infrahubctl` and nothing else.
HTTP `/api/*` calls, direct GraphQL POSTs, and
`docker compose exec` / `kubectl exec` into any
Infrahub-stack container (database, message queue,
task-manager-db, server, worker) for state inspection
are all out.

### Why it matters

Every other channel into the instance is a
**speculative** coupling to an internal implementation
detail that Infrahub explicitly does not commit to:

- HTTP routes (`/api/config`, `/api/schema/summary`,
  …) shift between versions; fields disappear,
  endpoints move. Today's `curl /api/foo` returns
  data; tomorrow's returns `{"detail": "not found"}`.
- GraphQL field names (`Branch.has_schema_changes`,
  `CoreGenericRepository.operational_status`, inline
  fragments on concrete repo kinds) shift between
  versions. A query that works on 1.9.6 raises
  `Cannot query field` on 1.10 — silently — and the
  bundle is now missing data the expert relies on.
- `cypher-shell` against the Neo4j container assumes
  a specific DB engine (Neo4j vs Memgraph),
  authentication shape, and procedure name (Neo4j 4's
  `CALL dbms.listQueries()` became Neo4j 5's `SHOW
  TRANSACTIONS`). Each upgrade silently moves the
  goalposts.
- `psql` against the task-manager-db container
  assumes a specific Prefect schema. Prefect minor
  upgrades have renamed columns and tables in the
  past.
- `rabbitmqctl` inside the message-queue container
  assumes the broker is RabbitMQ at all — if Infrahub
  ever swaps to another AMQP-compatible broker, the
  probe vanishes.
- `printenv`/`env` inside the server container
  assumes a specific env-var-driven config. The
  `INFRAHUB_*` names shift; some are now read from
  files, some from a secret manager.

`infrahubctl` is the only contract OpsMill commits
to. Its output format is part of the API surface.
When OpsMill changes `infrahubctl` output, that's
documented in release notes; when they change a
GraphQL field, an internal Cypher schema, or a
container env-var, it's not.

This rule is informed by a single live test against
Infrahub 1.9.6 (skill commit `20f0ad0`), where **six
classes of probe broke at once**: `/api/config`
returned a different shape, an inline-fragment
GraphQL query raised on a missing field, the Neo4j
`CALL dbms.listQueries()` call had been removed in
Neo4j 5, the `printenv INFRAHUB_DB_PASSWORD` probe
returned empty because the container reads from a
secret file, the Prefect Postgres query failed
because the column had been renamed, and the
`rabbitmqctl` call needed the cookie path which had
moved. Each individual fix would have been small;
the lesson is that no fix is the right fix —
removing the probe entirely is.

### What to do

Anything that needs instance state:

- Branches → `infrahubctl branch list` (text output;
  no `--json` on this subcommand) plus
  `infrahubctl branch report <name>` for detail.
- Repositories → `infrahubctl repository list`.
- Schemas → `infrahubctl schema list`,
  `infrahubctl schema show <kind>`,
  `infrahubctl schema export`,
  `infrahubctl schema check <files>`.
- Tasks → `infrahubctl task list` (with `--json`,
  `--include-logs`, `--include-related-nodes`,
  `-s <STATE>` filters).
- Telemetry → `infrahubctl telemetry export`.
- Versions → `infrahubctl version`,
  `infrahubctl info --detail`.

Anything that needs deployment-infrastructure state
(topology, container/pod logs, host fingerprint, the
user's local files): `docker compose ps/logs/config`,
`kubectl get/describe/logs`, `helm get values
history`, `uname`, `df`, `free`, reading
`.infrahub.yml` and `docker-compose.yml` off disk.
These inspect the **host and orchestration layer the
user controls**, not Infrahub internals, and are
fine.

If `infrahubctl` does not expose what you want,
**accept the gap**. Note it in the bundle's
`README.md`. Ask the user to paste output themselves
if they want to provide it (e.g., `curl /api/config`
into `bundle/baseline/api-config.json`, a Cypher
query result into a text file). The skill itself
does not probe.

### Compliant

```bash
# Branches
infrahubctl branch list > bundle/baseline/state/branches.txt

# Repositories
infrahubctl repository list > bundle/baseline/state/repositories.txt

# Tasks (here --json IS supported)
infrahubctl task list --json --limit 50 \
  > bundle/baseline/state/recent-tasks.json
```

### Non-compliant

```bash
# Direct GraphQL POST — speculative on field names
curl -sX POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"query { Branch { id name status }}"}' \
  > bundle/baseline/state/branches.json

# Direct DB peek — speculative on engine, version, auth
docker compose exec -T database cypher-shell -u neo4j -p "$X" \
  "MATCH (b:Branch) RETURN b.name, b.status, b.is_default;" \
  > bundle/category/branch-merge/neo4j/branches-raw.txt

# Direct queue depth — speculative on broker, cookie path
docker compose exec -T message-queue \
  rabbitmqctl list_queues name messages consumers \
  > bundle/category/task-worker-pipeline/rabbitmq/queues.txt

# Direct Postgres peek into Prefect — speculative on schema
docker compose exec -T task-manager-db psql -U postgres -d prefect -c \
  "SELECT id, state_type FROM flow_run ORDER BY start_time DESC LIMIT 50;" \
  > bundle/category/task-worker-pipeline/prefect/recent-runs.txt

# Env probe inside server container — speculative on var names + source
docker compose exec -T infrahub-server env | grep INFRAHUB_

# kubectl-exec equivalents of any of the above — same problem
kubectl -n infrahub exec "$DB_POD" -- cypher-shell -u neo4j -p "$X" ...
```

### Common mistakes

- **"But I already wrote the query, and I know it
  works on my version."** Yes, today. The next minor
  version moves the field, and the bundle silently
  drops the data. The user finds out from the
  expert, not from a clean error.
- **"`infrahubctl` doesn't expose what I want."**
  Accept the gap. Note it in `README.md`. Ask the
  user to paste the output if they want it included
  — that's their call, not the skill's automation.
- **"It's read-only, so it's fine."** Read-only is
  necessary but not sufficient. The brittleness
  argument is independent of mutation.
- **Confusing deployment infrastructure with the
  instance.** `docker compose ps`, `kubectl logs`,
  `docker stats`, `df -h`, reading
  `docker-compose.yml` are not "the instance" — they
  inspect what the user already controls and don't
  cross the contract.

Reference:
[docs.infrahub.app — infrahubctl](https://docs.infrahub.app/infrahubctl/infrahubctl).
Live-test corrections that informed this rule: commit
`20f0ad0` in this repository.
