---
title: audit-is-read-only
impact: CRITICAL
tags: audit, conduct, git
---

# Rule: audit-is-read-only

**Severity**: CRITICAL
**Category**: Conduct

## What It Checks

This rule constrains the auditor rather than the
repository. An audit observes and reports. It never
writes to the working tree, the index, or the
repository's data. Every other rule in this skill
describes something to look for; this one describes
how to look without changing what you are looking at.

Read it before Phase 1, not after Phase 9.

## Why it matters

An audit is most useful on a tree that has
uncommitted changes, because that is the normal state
during development. That is also the state where a
write is unrecoverable. You cannot tell by looking
whether uncommitted work in the tree is the user's,
another agent's, or a stale leftover, and the tree
carries no undo.

The destructive step is usually the **cleanup**, not
the original write. An audit that dirties the tree
and then tidies up after itself with
`git checkout --` over a directory will delete
whatever else was in that directory. That has
happened: an audit stashed a generator, ran it, then
reverted the output directory, and destroyed another
agent's regenerated files. Recovery needed a restore
from a commit's parent, and the loss was noticed only
because someone compared file modification times.

The report was correct and said nothing about the
tree having been modified, because nothing told the
auditor that modifying the tree was worth mentioning.

## Checks

1. **Never write to the tree or the index.** No file
   creation, edit, move, or delete outside the report
   file itself.
2. **Never run a destructive git command against a
   tree being audited**, *including to undo your own
   side effect*:

   ```text
   git checkout      git restore     git stash
   git clean         git reset       git rm
   ```

   The "including to undo your own side effect"
   clause is the load-bearing half. A revert run in
   the belief that it is tidying up is still a
   delete.
3. **Read another revision with a read-only command.**
   All of these read without touching the tree:

   ```bash
   git show <ref>:<path>          # one file at one revision
   git diff <ref> -- <path>       # what changed
   git cat-file -p <ref>:<path>   # same, plumbing
   git ls-tree -r --name-only <ref>   # what exists at that ref
   ```

   This is how you compare committed content against
   a dirty tree without stashing anything.
4. **Before running any repository script for its
   output, establish whether it writes.** Read the
   script. A flag named `--check`, `--dry-run`, or
   `--validate` is a naming convention, not a
   guarantee. If you cannot establish it from the
   source, do not run it: report the check as not
   performed and say why.
5. **If you have already dirtied the tree, say so in
   the report and leave it.** Name the paths you
   touched. A visible mess is recoverable; a silent
   revert is not.
6. **State the tree's condition in the report.** If
   the audit ran against a tree with uncommitted
   changes, record that, because it bounds what the
   findings are worth. See
   [deployment-readiness](./deployment-readiness.md),
   which already asks whether the tree is clean for a
   different reason.

## Common Issues

- `git stash push` before running something, `git stash
  pop` after. Cheap-looking, and it silently
  reorders or drops another writer's concurrent
  changes.
- `git checkout -- <dir>` to undo a generator's
  output. Deletes every uncommitted file in that
  directory, not only the ones you caused.
- Running a generator or loader with `--check`
  assuming it is read-only. Several project scripts
  write in check mode.
- Reporting findings that required a write without
  mentioning the write, so the reader cannot tell the
  tree changed under them.
- Reaching for a stash to get at committed content
  when `git show <ref>:<path>` answers the same
  question without touching anything.
