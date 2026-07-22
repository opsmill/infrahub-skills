# Examples — analyzing a diagnostic bundle

End-to-end walk-throughs: bundle contents in,
findings report out. Adapt the shape, not the
specific errors.

## Example 1: crash cascade (database OOM)

### Bundle contents (abridged)

`bundle/bundle_information.json`:

```json
{
  "deployment": {"type": "docker-compose", "project": "infrahub-prod"},
  "collectors": [
    {"name": "logs/server", "status": "ok"},
    {"name": "logs/database", "status": "ok"},
    {"name": "logs/task-worker", "status": "ok"},
    {"name": "logs/message-queue", "status": "failed",
     "error": "container not running"}
  ]
}
```

`bundle/logs/database/database-1.log`:

```text
2026-07-18 14:02:11.408+0000 ERROR ... java.lang.OutOfMemoryError: Java heap space
```

`bundle/logs/server/infrahub-server-1.log` —
41 lines between 14:02:19 and 14:05:40 like:

```text
2026-07-18 14:02:19 ERROR infrahub.database Unable to connect to database: Connection refused
```

`bundle/logs/task-worker/task-worker-1.previous.log`
(tail):

```text
2026-07-18 14:03:05 ERROR ... database connection timeout (attempt 12/12)
2026-07-18 14:03:07 CRITICAL worker shutting down
```

### Findings report

```markdown
# Findings — infrahub-prod bundle (collected 2026-07-18 14:11)

Manifest: 3/4 log collectors succeeded.
`logs/message-queue` collection failed ("container
not running") — treated as finding, see Incident 1.

## Incident 1: database OOM cascading to server and task-worker (CRITICAL)

- Window: 14:02:11 → 14:05:40
- Root: database out of memory —
  bundle/logs/database/database-1.log
  > 14:02:11 ERROR ... java.lang.OutOfMemoryError: Java heap space
- Cascade:
  - 41 server connection errors, 14:02:19-14:05:40
    (bundle/logs/server/infrahub-server-1.log)
  - task-worker-1 killed and restarted at 14:03:07
    (bundle/logs/task-worker/task-worker-1.previous.log, tail)
  - message-queue container not running at
    collection time (manifest) — consistent with the
    same resource pressure, but the bundle has no
    message-queue log to confirm.
- Known issue: no exact match.
  Queries tried: `gh search issues --repo
  opsmill/infrahub --state all "OutOfMemoryError
  neo4j heap"`; second pass "database OOM".
- Open questions: what drove heap usage before
  14:02 — a next bundle with `--include-queries`
  and `--benchmark` would show active queries and
  host sizing.
- Recommendation (not executed here): hand bundle +
  this report to OpsMill support; heap sizing is
  the likely conversation.
```

Note what the report does: manifest failure promoted
to evidence, one incident instead of three findings,
every claim carries a path + excerpt, the GitHub
queries are recorded even though they found nothing,
and the missing data is an open question mapped to
`create` flags — not a guess.

## Example 2: traceback matched to a known issue

### Bundle contents (abridged)

`bundle/logs/server/infrahub-server-1.log`:

```text
2026-07-20 09:14:52 ERROR infrahub.graphql Traceback (most recent call last):
  File "/usr/local/lib/python3.12/site-packages/infrahub/graphql/mutations/proposed_change.py", line 142, in mutate
    schema = registry.get_schema(name=kind, branch=branch)
  File "/usr/local/lib/python3.12/site-packages/infrahub/core/registry.py", line 88, in get_schema
    raise SchemaNotFoundError(...)
infrahub.exceptions.SchemaNotFoundError: Unable to find the schema 'CoreProposedChange' in the registry for branch 'atl-fix-vlans-0f3aa9c2'
```

### Key construction and search

Stable parts: exception class
`SchemaNotFoundError`, message fragment
`Unable to find the schema` + kind
`CoreProposedChange`, innermost Infrahub frame
`core/registry.py`. Stripped: branch name
`atl-fix-vlans-0f3aa9c2` (volatile — unique to this
deployment).

```bash
gh search issues --repo opsmill/infrahub --state all "SchemaNotFoundError CoreProposedChange"
```

### Findings report (excerpt)

```markdown
## Incident 1: SchemaNotFoundError on proposed-change mutation (HIGH)

- Root: SchemaNotFoundError —
  bundle/logs/server/infrahub-server-1.log
  > SchemaNotFoundError: Unable to find the schema
  > 'CoreProposedChange' in the registry for branch '...'
  Raised from infrahub/core/registry.py via
  graphql/mutations/proposed_change.py.
- Known issue: opsmill/infrahub#4102 (closed —
  fixed in 1.1.6) matches the traceback. Server here
  runs 1.1.3 (bundle/server/): upgrading past 1.1.6
  should resolve it.
- Next step: if you want to confirm on the issue or
  add your reproduction, continue with
  infrahub-reporting-issues — this analysis does not
  post to GitHub.
```

The closed match is the payoff of `--state all`:
the answer is "already fixed, upgrade", not a new
issue. Version evidence comes from the bundle
(`bundle/server/`), and the hand-off names the
sibling skill instead of running `gh issue create`.
