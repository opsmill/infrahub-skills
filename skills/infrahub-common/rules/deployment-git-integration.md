---
title: Git Repository Integration for Infrahub Code
impact: CRITICAL
tags: deployment, git, repository, sync, infrahub-yml, generators, checks, transforms
---

## Git Repository Integration for Infrahub Code

Impact: CRITICAL

Infrahub discovers generators, checks, transforms,
GraphQL queries, and `.infrahub.yml` by cloning the
**committed** state of a registered git repo. Files
sitting uncommitted in the working tree are invisible
to it.

### Why it matters

The import step clones the configured ref into the
task-worker container, then runs `.infrahub.yml`
against that clone. Any file you forgot to commit
simply isn't there, so the loader either skips the
definition silently (no error, just nothing happens)
or fails on a missing import when a check references
a queries file that never landed.

This is the only production path for **checks,
generators, transforms, and artifact definitions**.
Infrahub executes those from the repo clone, so a
check that is not in an imported repo gates nothing
and a generator that is not in an imported repo never
fires automatically. `infrahubctl check` and
`infrahubctl generator` run them against your local
filesystem, which is a development loop, not a
deployment.

Schemas and objects are different: they can be applied
directly with `infrahubctl schema load` and
`infrahubctl object load`, and on most deployments that
is the preferred route.

### Getting a change picked up

Three steps, and the third is the one people miss:

1. **Commit.** Always required. The worker reads
   committed git state.
2. **Push, but only if the registered `location` is
   a remote URL.** When the repo is mounted into the
   task-worker as a local volume (`location:
   "/upstream"`), the commit alone is enough, since
   the worker clones from that path directly.
3. **Trigger the import** if the repo is read-only.
   A `CoreReadOnlyRepository` does not poll. See the
   table below.

### Repository types

| | `CoreReadOnlyRepository` | `CoreRepository` |
| --- | --- | --- |
| Tracks | one ref, set by `ref` (branch, tag, or commit) | every branch on the remote; `default_branch` names the one mapped to Infrahub's default |
| Import | **never automatic.** Only when you change `ref`, or run the **Import latest commit** action (`InfrahubReadOnlyRepositoryImportLastCommit`) | **automatic.** Background tasks poll the remote several times a minute and re-import on change |
| Infrahub branches | creates none | creates a matching Infrahub branch for every Git branch (branch parity) |
| Writes back to Git | never | pushes the linked branch when a proposed change merges |

The automatic import is why `CoreRepository` is the
riskier default: every push to any branch is imported
without review. `CoreReadOnlyRepository` makes each
import a deliberate act, which is usually what you
want.

```yaml
# bootstrap/local-dev-repo.yml
# Load manually, NOT in objects/
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreReadOnlyRepository
  data:
    - name: my-repo
      location: "/upstream"    # Or HTTPS URL
      ref: "branch-name"      # Git branch/tag
```

Use `CoreRepository` only when Infrahub genuinely
needs to write back to the repo:

```yaml
spec:
  kind: CoreRepository
  data:
    - name: my-repo
      location: "/upstream"
      default_branch: "main"
```

**Warning**: `CoreRepository` tries to push to remote
when setting up branch worktrees. This fails with
local `/upstream` mounts if the remote isn't
writable.

### `sync_with_git` does not control importing

Every Infrahub branch carries a `sync_with_git`
property, chosen when the branch is created. It
controls whether a branch created **in Infrahub** is
extended **out to Git**: with it on, Infrahub creates
a matching branch in every read-write repository and
merges that branch in Git when a proposed change
merges.

It does not gate importing. Import always runs from
Git into Infrahub regardless of this property. The
name reads the other way round, which is the usual
source of confusion. Data-only changes generally need
no Git branch at all, since that data lives only in
the graph.

### Local Development Setup

For local development, mount the repo into the
task-worker container:

```yaml
# docker-compose.override.yml
services:
  task-worker:
    volumes:
      - ./:/upstream
```

### Common Pitfalls

- **Uncommitted changes are invisible**: the worker
  clones the committed git state, not the working
  directory, so uncommitted files behave as if they
  don't exist, with no error to flag them
- **Committed but not pushed, on a remote repo**: the
  worker clones the remote, so a local commit that
  was never pushed is just as invisible. Only a
  locally mounted `location` is exempt
- **Worker race conditions**: with 2+ task workers,
  both can try to import the new repo simultaneously
  and hit uniqueness constraint errors. Scale to 1
  worker for initial repo creation, then scale back
- **Bootstrap files in objects/**: keep the repo
  definition file out of `objects/`, since everything
  in there is auto-imported during sync, which
  produces validation errors or circular dependencies
  when the repo tries to register itself. Use a
  separate `bootstrap/` directory
- **Waiting for a read-only repo to re-sync**: it
  never will on its own. Run **Import latest commit**
  or change the `ref`. Do **not** delete and re-create
  the registration, which is destructive and
  unnecessary
- **Treating `ok: true` as "imported"**: the mutation
  returns when the import is *dispatched*, not when it
  finishes. Confirm by checking the repository's
  recorded commit and sync status

Reference:
[Git integration](https://docs.infrahub.app/git-integration/overview),
[Connect a repository](https://docs.infrahub.app/git-integration/connect-repository),
[infrahub-yml-reference.md](../infrahub-yml-reference.md)
