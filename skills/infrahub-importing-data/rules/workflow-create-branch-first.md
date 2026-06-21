---
title: Create the Import Branch Before Validate or Load
impact: CRITICAL
description: >-
  Run `infrahubctl branch create <name>` after the self-check passes and
  before validate/load. Branch-first means a failed load is discarded with
  one `branch delete`, never reconciled on the default branch.
tags: workflow, branch, infrahubctl, validate, load
---

## Create the Import Branch Before Validate or Load

Impact: CRITICAL

Run `infrahubctl branch create <name>` **after** the
local self-check passes and **before**
`infrahubctl object validate` or `object load`.
Both commands fail if the branch doesn't exist.

Create the branch AFTER the self-check so a
shape-error emission doesn't leave an orphan branch
on the server.

### The commands

```bash
# 1. After the local self-check passes:
infrahubctl branch create csv-import-20260621-1430

# 2. Validate the emission against the branch:
infrahubctl object validate ./output_dir/ --branch csv-import-20260621-1430

# 3. Load on success:
infrahubctl object load ./output_dir/ --branch csv-import-20260621-1430

# 4. If anything fails partway, discard the branch:
infrahubctl branch delete csv-import-20260621-1430
```

Never load to the default branch. Object load is
not transactional across files — a partial failure
leaves the branch in a mixed state. On a dedicated
branch cleanup is one `branch delete`; on the
default branch it's per-object cleanup. See
[../../infrahub-managing-objects/rules/workflow-branch-first.md](../../infrahub-managing-objects/rules/workflow-branch-first.md).

### Common mistakes

- **Running `object load --branch my-branch`
  without creating `my-branch` first.** The load
  fails with branch-not-found.
- **Creating the branch before the self-check.**
  Leaves orphan branches when the self-check fails.
- **Trying to resume a partial load.** Not
  supported. Discard the branch, re-run with a
  fresh branch name.

Reference: [Infrahub Branches & Proposed Changes](https://docs.infrahub.app/topics/proposed-change)
