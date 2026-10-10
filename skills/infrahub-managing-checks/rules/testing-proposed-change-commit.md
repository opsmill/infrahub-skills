---
title: Which Commit a Proposed Change's Checks Run
impact: MEDIUM
tags: testing, proposed-change, git, commit, rebase, sync_with_git
---

## Which Commit a Proposed Change's Checks Run

Impact: MEDIUM

A proposed change runs its checks with the code at the
repository commit recorded on its source branch, not the
latest commit on `main`. On a branch synced with Git,
`infrahubctl branch rebase` does not change that commit,
and `CoreProposedChangeRunCheck` (the "Retry" button on
the checks) reruns the same commit.

### Why it matters

After a check fix is merged to `main`, open proposed
changes keep failing with the old message. A rebase and
a retry both succeed with no error, so the fix looks
broken when the old code is still what runs.

### Is the branch synced with Git?

`infrahubctl branch list` shows it. How the branch was
created sets it:

- GraphQL `BranchCreate` without `sync_with_git`: synced.
- SDK `client.branch.create`: synced in SDK 1.20 and
  earlier. From SDK 1.21.0 the default is
  `sync_with_git=False`.
- `infrahubctl branch create`: synced only with
  `--sync-with-git`.

This rule covers branches synced with Git. Each one has
a Git branch of the same name in the repository, and its
recorded commit moves only when that Git branch moves.

### Get new check code into an open proposed change

1. Merge or rebase `main` into the Git branch with the
   same name as the source branch, and push it.
2. Wait for the repository sync to record the new commit
   on the branch. The sync runs about once a minute.
3. Rerun the checks with `CoreProposedChangeRunCheck` or
   the "Retry" button.

Or open a new branch and a new proposed change after the
fix is on `main`. The new branch starts from the current
commit.

While writing or fixing the check, run it locally first.
`infrahubctl check <name> --branch <branch>` runs your
working copy against the branch's data, with no commit
or push. It does not update the proposed change's check
status.

### Incorrect

```bash
# Rebase and retry: on a synced branch the old commit runs again
for b in $branches; do
  infrahubctl branch rebase "$b"
done
# ...then CoreProposedChangeRunCheck for each proposed change
```

### Correct

```bash
# Move each source branch's Git branch, then rerun the checks
git clone --quiet "$REPO_URL" repo && cd repo
for b in $branches; do
  git checkout "$b"
  git merge --no-edit origin/main
  git push origin "$b"
done
sleep 120   # let the repository sync record the new commits
# ...then CoreProposedChangeRunCheck for each proposed change
```

Reference:
[Infrahub proposed changes](https://docs.infrahub.app/topics/proposed-change)
