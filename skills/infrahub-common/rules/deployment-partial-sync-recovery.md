---
title: Recovering from a Partial Repository Sync
impact: HIGH
tags: deployment, recovery, CoreReadOnlyRepository, sticky-state
---

## Recovering from a Partial Repository Sync

Impact: HIGH

A mid-import failure on a `CoreReadOnlyRepository`
(or `CoreRepository`) can leave the repo in a
state where `--ref` updates don't retrigger the
import and deletion hits relationship-constraint
errors on `CoreRepositoryGroup`. The repo's
`location` attribute is `unique=True`, so the
escape hatch is to re-serve the bundle under a
different URL and register a fresh repo.

### Why it matters

The repo import writes state incrementally as it
walks the bundle (repository row → branch row →
group memberships → per-section ingest). When the
worker fails partway through, the writes that
already landed stay visible but the repo never
advances to the new commit. The natural instincts
— re-pull, or delete-and-recreate — both fail:
the worker doesn't reschedule, and deletion is
blocked by the `optional: false` group-back-link.
The exact worker-side state machine isn't
publicly documented, but the unique-URL +
mandatory-back-link facts are enough to know that
a new URL is a clean new registration.

### Symptoms

| What you see | What it means |
| ------------ | ------------- |
| Update with new `--ref` returns ok, repo stays on old commit | The worker isn't rescheduling after the failure; the update API write succeeded but no pull was queued |
| `delete CoreReadOnlyRepository` returns `foreign key constraint` | The mandatory `CoreRepositoryGroup → repository` link blocks deletion until the groups are detached |
| Logs show one bad file, rest of the bundle is fine | The import rolled forward through the good entries before tripping on the malformed one |

### Recovery Steps

Don't try to clean the existing repo row in place —
the constraints are correct, and untangling them by
hand is fragile. The repeatable fix:

1. **Fix the underlying file.** Run
   `infrahubctl schema check <dir>` and
   `infrahubctl render <transform>` locally
   against the committed file set until everything
   loads cleanly outside of the repo pipeline. If
   you skip this step, every retry below will leave
   the new repo in the same sticky state.

2. **Serve the repository under a new path or
   port.** The repo registration is keyed by URL,
   so changing the URL (e.g.
   `http://host/git/devnet.git` →
   `http://host/git/devnet-v2.git`) makes a fresh
   registration possible without untangling the
   stuck one. A new branch on the same URL is
   *not* enough — the repo row keys on URL.

3. **Register the new path as a
   `CoreReadOnlyRepository`** (or `CoreRepository`)
   pointing at the same fixed commit. This is a
   fresh worker run with no stale state.

4. **Leave the stuck repo alone or rename it for
   cleanup.** Once the new repo is healthy, the
   stuck one can be excluded from any artifact
   target groups so it no longer affects pipelines.
   Hard-deletion remains blocked but is no longer
   on the critical path.

### Prevention

The sticky state is only triggered by an import
failure, so the prevention is to keep imports from
failing on a new repo:

- Run `infrahubctl schema check schemas/` locally
  before committing any schema change. The check
  catches the malformations that trip the worker.
- Run `infrahubctl render` and
  `infrahubctl transform` against every transform
  before registering the repo. The pipeline runs
  the same code path; local success means import
  success.
- Stage repo changes on a fork or branch before
  pointing the production repo at a new commit.
  See
  [deployment-git-integration.md](./deployment-git-integration.md)
  for the commit-and-push lifecycle the worker
  expects.

### Related

- [deployment-git-integration.md](./deployment-git-integration.md)
  — the normal lifecycle this rule is the recovery
  path for.
- [../../infrahub-managing-transforms/rules/testing-commands.md](../../infrahub-managing-transforms/rules/testing-commands.md)
  — the local-render vs artifact-pipeline split
  that this rule lives at the failure boundary of.

Reference: [Infrahub Repository Docs](https://docs.infrahub.app)
