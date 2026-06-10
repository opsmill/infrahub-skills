---
title: Git Repository Integration for Infrahub Code
impact: CRITICAL
tags: deployment, git, repository, sync, infrahub-yml, generators, checks, transforms
---

## Git Repository Integration for Infrahub Code

Impact: CRITICAL

Infrahub discovers generators, checks, transforms,
GraphQL queries, and `.infrahub.yml` by cloning the
**committed** state of a registered git repo — files
sitting uncommitted in the working tree are invisible
to it.

### Why it matters

The sync step clones HEAD of the configured ref into
the task-worker container, then runs `.infrahub.yml`
against that clone. Any file you forgot to commit
simply isn't there, so the loader either skips the
definition silently (no error, just nothing happens)
or fails on a missing import when a check references
a queries file that never landed. Setup order
matters for the same reason: the repo registration
triggers an immediate sync, so the schema and any
referenced objects need to exist on the server
before the worker tries to validate the
`.infrahub.yml` against them.

### Requirements

1. **Commit every referenced file before registering
   the repo**: `.infrahub.yml`, `generators/*.py`,
   `checks/*.py`, `transforms/*.py`, `queries/*.gql`
2. **A git repository must be registered** in
   Infrahub pointing to the repo
3. **The repo must sync successfully** before
   definitions are available
4. **Setup order matters**: Load schema first, create
   the Infrahub branch, load objects, THEN register
   the git repo

### CoreReadOnlyRepository (Recommended for Code-Only Repos)

Use `CoreReadOnlyRepository` when the repo only
provides code (generators, checks, transforms,
queries, schemas). It does not try to push back to
the remote, avoiding worktree errors with local
mounts.

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

Key differences from `CoreRepository`:

- Uses `ref` attribute (not `default_branch`)
- Does not push to remote (no worktree errors with
  local mounts)
- No periodic sync -- imports once at creation time
  only
- Suitable for generators, checks, transforms, and
  schema code

### CoreRepository (When Infrahub Needs Write Access)

Use `CoreRepository` when Infrahub needs to write
back to the repo (e.g., generated configs):

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
  directory — uncommitted files behave as if they
  don't exist, with no error to flag them
- **Worker race conditions**: with 2+ task workers,
  both can try to import the new repo simultaneously
  and hit uniqueness constraint errors. Scale to 1
  worker for initial repo creation, then scale back
- **Bootstrap files in objects/**: keep the repo
  definition file out of `objects/` — everything in
  there is auto-imported during sync, which produces
  validation errors or circular dependencies when
  the repo tries to register itself. Use a separate
  `bootstrap/` directory
- **Read-only repos don't re-sync**:
  `CoreReadOnlyRepository` imports once at creation
  time. To pick up new commits, delete and re-create
  the repo registration

Reference:
[infrahub-yml-reference.md](../infrahub-yml-reference.md)
