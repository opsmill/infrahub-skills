---
title: Git Repository Integration for Infrahub Code
impact: CRITICAL
tags: deployment, git, repository, sync, infrahub-yml, generators, checks, transforms
---

## Git Repository Integration for Infrahub Code

Impact: CRITICAL

All executable code (generators, checks, transforms),
GraphQL queries, and `.infrahub.yml` must be committed to
git and synced via a `CoreRepository` or
`CoreReadOnlyRepository` for Infrahub to discover and
execute them. Infrahub reads these files from the
**committed** git state, not the working directory.

### Requirements

1. **All files must be committed**:
   `.infrahub.yml`, `generators/*.py`, `checks/*.py`,
   `transforms/*.py`, `queries/*.gql`
2. **A git repository must be registered** in Infrahub
   pointing to the repo
3. **The repo must sync successfully** before definitions
   are available
4. **Setup order matters**: Load schema first, create
   Infrahub branch, load objects, THEN register the git
   repo

### CoreReadOnlyRepository (Recommended for Code-Only Repos)

Use `CoreReadOnlyRepository` when the repo only provides
code (generators, checks, transforms, queries, schemas).
It does not try to push back to the remote, avoiding
worktree errors with local mounts.

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
- No periodic sync -- imports once at creation time only
- Suitable for generators, checks, transforms, and
  schema code

### CoreRepository (When Infrahub Needs Write Access)

Use `CoreRepository` when Infrahub needs to write back
to the repo (e.g., generated configs):

```yaml
spec:
  kind: CoreRepository
  data:
    - name: my-repo
      location: "/upstream"
      default_branch: "main"
```

**Warning**: `CoreRepository` tries to push to remote
when setting up branch worktrees. This fails with local
`/upstream` mounts if the remote isn't writable.

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

- **Uncommitted changes are invisible**: Infrahub reads
  from committed git, not the working directory
- **Worker race conditions**: When creating a repo with
  2+ task workers, both may try to import simultaneously
  causing uniqueness constraint errors. Scale to 1 worker
  for initial repo creation, then scale back
- **Bootstrap files in objects/**: Don't put repo
  definition files in `objects/` -- Infrahub auto-imports
  everything there during sync, causing validation errors
  or circular dependencies. Use a separate `bootstrap/`
  directory
- **Read-only repos don't re-sync**:
  `CoreReadOnlyRepository` imports once at creation time.
  To pick up new commits, delete and re-create the repo
  registration

Reference:
[infrahub-yml-reference.md](../infrahub-yml-reference.md)
