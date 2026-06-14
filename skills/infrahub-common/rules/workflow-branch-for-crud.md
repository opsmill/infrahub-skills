---
title: Do Data CRUD on a Branch, Not the Default Branch
impact: CRITICAL
tags: branch, default-branch, crud, object-load, proposed-change, rollback, mcp
---

## Do Data CRUD on a Branch, Not the Default Branch

Impact: CRITICAL

When creating, updating, or deleting data in Infrahub —
whether via `infrahubctl object load`, the MCP
`infrahub_create` / `infrahub_update` / `infrahub_delete`
tools, `infrahubctl generator run`, or the Python SDK —
default to working on a dedicated branch. Reach for the
**default branch** (the branch operations target when no
branch is given — `main` by convention, but it can be
renamed per deployment, so confirm with
`infrahubctl branch list` rather than assuming `main`) only
on a local, throwaway instance you are willing to discard.

### Why it matters

The default branch is the source of truth everyone reads,
and Infrahub gives no "undo" for a write that lands there.

- **Rollback is per-object, not per-changeset.** Undoing a
  bad bulk write to the default branch means deleting each
  object by hand; a branch is one discard. The asymmetry
  scales with the write — a 38,000-object import gone wrong
  is 38,000 deletions on the default branch versus a single
  discard on a branch.
- **Writes to the default branch skip review.** The
  proposed-change pipeline — schema validation, checks,
  conflict detection, human review — runs only on merge, so
  a write straight to the default branch lands unreviewed.

### The safe pattern

1. Create or select a dedicated branch
   (`infrahubctl branch create my-change`, or pass
   `--branch` / the `branch` argument on the operation).
   `infrahubctl branch list` shows what already exists.
2. Do the create/update/delete on that branch.
3. Validate on the branch (e.g.
   `infrahubctl object validate ... --branch my-change`,
   or re-query the branch) and let checks run.
4. Merge via a proposed change in the UI when it looks
   right — or discard the branch if it doesn't
   (`infrahubctl branch delete my-change`).

`infrahubctl branch <create|list|delete>` is the CLI entry
point for managing these branches.

### When the default branch is acceptable

A local development instance or disposable sandbox you can
wipe and rebuild — the branch ceremony buys nothing there.
On any shared or production instance, work on a dedicated
branch.

### Rationalizations under pressure

A deadline is when a non-recoverable mistake costs the most
— and when the excuses for skipping the branch get loudest.
The branch is two commands and ~10–60 seconds, and it is
the *recoverable* path a deadline actually needs. On a
shared instance, none of these hold:

| Excuse | Reality |
| ------ | ------- |
| "No time for branch ceremony — just give me the one command." | The bare command writes to whatever branch the CLI targets — usually the default branch — with no undo. The branch path costs seconds and is what makes the deadline survivable if the write is wrong. |
| "It's additive / a small change / zero risk." | That framing precedes most incidents. The write hits the live graph immediately; a wrong value or a mid-batch error lands on the data everyone reads, and "small" still can't be undone in one step. |
| "I'll just delete/revert it afterward if it's wrong." | Cleanup on the default branch is per-object and manual, and loads aren't transactional, so a partial failure leaves it half-written. Discarding a branch is one action. |
| "It validated / `check` passed, so the write is safe." | `validate` / `check` previews shape; it does not apply the change or catch every load-time failure. Run the write on a branch so it stays reversible. |
| "It's basically our sandbox." | The escape hatch is a *local, disposable* instance. A shared or production instance is not a sandbox just because it is convenient to treat it as one. |

### Red flags — stop and put it on a branch

- About to run a create/update/delete with no `--branch` /
  no `branch` argument on a shared server.
- Typing the default branch's name as the target of a write.
- Reassuring yourself with "just this once", "in a hurry",
  "additive", or "I'll clean it up after".
- Calling a shared instance a "sandbox" to justify skipping
  the branch.

**Following the letter of the rule while skipping the branch
on a shared instance still violates its spirit.** All of
these mean: create a branch, make the change there,
validate, and merge via a proposed change. The one genuine
exception is a local throwaway instance — the branch is
cheap and the mistake it prevents is not.

Reference:
[Infrahub Branches & Proposed Changes](https://docs.infrahub.app/topics/proposed-change)
