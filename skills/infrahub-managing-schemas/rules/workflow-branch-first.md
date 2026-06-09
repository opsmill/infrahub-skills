---
title: Load Schema Changes onto a Branch, Not the Default Branch
impact: CRITICAL
tags: branch, default-branch, schema-load, migration, infrahubctl, proposed-change
---

## Load Schema Changes onto a Branch, Not the Default Branch

Impact: CRITICAL

Apply schema changes on a dedicated branch first, not
directly to the **default branch** (the branch
`schema load` targets when no `--branch` is given — `main`
by convention, but it can be renamed per deployment), on
any shared server. `infrahubctl schema load` defaults to
the default branch when no `--branch` is given — make the
branch explicit. (The default branch is acceptable only on
a local, throwaway instance you can wipe and rebuild.) This
is the schema application of the shared rule
[../../infrahub-common/rules/workflow-branch-for-crud.md](../../infrahub-common/rules/workflow-branch-for-crud.md).

### Why it matters

A schema load on the default branch mutates the live data
model the whole team reads, immediately and globally.
Schema changes are not just additive: a migration that
drops an attribute (`state: absent`), tightens a
constraint, or changes a kind **runs against the data
already loaded** the moment the schema lands. On the
default branch there is no preview and no per-step undo — a
wrong migration has already rewritten or deleted data by
the time you notice.

On a dedicated branch you get the safety the change
deserves: `infrahubctl schema check --branch` shows the
diff before anything is written, the load is isolated to
that branch, and merging goes through a proposed change
where validation and checks run. If the migration is wrong,
you delete the branch instead of reconstructing data on the
default branch.

### The workflow

Branches are managed with `infrahubctl branch`:

```bash
# See what branches already exist
infrahubctl branch list

# Create a branch for the schema change
infrahubctl branch create schema-add-maint-window

# Preview the diff, then load onto that branch
infrahubctl schema check schemas/ --branch schema-add-maint-window
infrahubctl schema load  schemas/ --branch schema-add-maint-window

# Inspect on the branch; merge via a proposed change in the UI
# when correct — or discard the branch entirely:
infrahubctl branch delete schema-add-maint-window
```

See [../validation.md](../validation.md) for the full
check/load reference and
[migration-state-absent.md](./migration-state-absent.md)
for staging destructive migrations.

### Common mistakes

- `infrahubctl schema load schemas/` (no `--branch`)
  against a shared server as the default — the migration
  runs on the default branch immediately.
- Assuming the default branch is always `main` — it is
  whatever the deployment configured; `infrahubctl branch
  list` shows the real branches.
- Treating `infrahubctl schema check` as enough safety on
  its own — `check` shows the diff but `load` is what
  mutates data; run the `load` on a branch so the mutation
  is reversible by discarding the branch.
- Rolling out a destructive migration (`state: absent`,
  type change) directly on the default branch "because it
  validated" — validation does not undo the data loss the
  migration causes.

### Red flags — stop and load onto a branch

- "It's just one optional attribute, totally additive, zero
  risk" — additive-looking schema changes still apply to
  the live graph immediately and can't be undone per-step
  on the default branch; Dropdown `choices` are a contract,
  so wrong values now become a migration later.
- "`schema check` passed, so I'll `schema load` onto the
  default branch" — `check` previews the diff; `load` is
  the mutation. Run the `load` on a branch.
- Rolling out a migration on the default branch under
  incident/deadline pressure because "there's no time for
  branches" — the branch is ~60 seconds and is the only
  rollback you get.

These are the schema cases of the shared rationalization
table in
[../../infrahub-common/rules/workflow-branch-for-crud.md](../../infrahub-common/rules/workflow-branch-for-crud.md),
which also covers when the default branch is acceptable (a
local throwaway instance only).

Reference:
[Infrahub Branches & Proposed Changes](https://docs.infrahub.app/topics/proposed-change)
