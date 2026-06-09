---
title: Load Objects onto a Branch, Not the Default Branch
impact: CRITICAL
tags: branch, default-branch, object-load, infrahubctl, proposed-change, rollback
---

## Load Objects onto a Branch, Not the Default Branch

Impact: CRITICAL

Before running `infrahubctl object load` against a shared
server, create or select a dedicated branch and load onto
it. Loading straight to the **default branch** (the branch
`object load` targets when no `--branch` is given — `main`
by convention, but it can be renamed per deployment) is
only reasonable on a local throwaway instance. This is the
object-loading application of the shared rule
[../../infrahub-common/rules/workflow-branch-for-crud.md](../../infrahub-common/rules/workflow-branch-for-crud.md).

### Why it matters

`infrahubctl object load` defaults to the default branch
when no `--branch` is given, so an unqualified load on a
shared server writes straight to the source of truth —
carrying the per-object cleanup cost the shared rule
describes (a bad bulk load is unwound one object at a time,
versus a single branch discard).

What's specific to object loads: they are **not
transactional across files**. If file 17 of 20 fails
partway through, files 1–16 are already written to whatever
branch you targeted. On a dedicated branch you throw the
partial state away; on the default branch you clean it up
by hand. Loading onto a branch also routes the change
through a proposed change, so schema validation and checks
run before the data reaches the default branch.

### The workflow

Branches are managed with `infrahubctl branch`:

```bash
# 1. See existing branches, then create one for the load
infrahubctl branch list
infrahubctl branch create import-q1

# 2. Validate, then load onto that branch
infrahubctl object validate objects/ --branch import-q1
infrahubctl object load objects/ --branch import-q1

# 3. Inspect on the branch; merge via a proposed change in
#    the UI when correct — or discard it entirely:
infrahubctl branch delete import-q1
```

See [../validation.md](../validation.md) for the full
validate/load command reference and the pre-load checklist.

### Common mistakes

- `infrahubctl object load objects/` with no `--branch` on
  a shared server — it lands on the default branch.
- Assuming the default branch is always `main` — it is
  whatever the deployment configured; `infrahubctl branch
  list` shows the real branches.
- Treating "I'll just delete the objects if it's wrong" as
  a recovery plan instead of loading onto a discardable
  branch.
- Loading a large, only-partially-validated batch directly
  to the default branch because "it worked in the validate
  dry run" — validate doesn't catch every load-time
  failure, and a mid-batch failure leaves the default
  branch partially written.

### Red flags — stop and load onto a branch

- About to run `infrahubctl object load objects/` with no
  `--branch` on a shared server — it lands on the default
  branch.
- Telling yourself "I'll just delete the objects if the
  import is wrong" — that is the per-object cleanup a
  discardable branch exists to avoid.
- Firing a large batch straight at the default branch under
  time pressure because the dry-run validated.

These are the object-loading cases of the shared
rationalization table in
[../../infrahub-common/rules/workflow-branch-for-crud.md](../../infrahub-common/rules/workflow-branch-for-crud.md),
which also covers when the default branch is acceptable (a
local throwaway instance only).

Reference:
[Infrahub Branches & Proposed Changes](https://docs.infrahub.app/topics/proposed-change)
