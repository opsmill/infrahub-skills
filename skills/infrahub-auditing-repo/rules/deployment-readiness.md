---
title: deployment-readiness
impact: MEDIUM
tags: audit, deployment
---

# Rule: deployment-readiness

**Severity**: MEDIUM
**Category**: Deployment

## What It Checks

Validates the repository is ready for deployment to
Infrahub — git tracking, bootstrap placement, load
ordering, and display-label safety during batch
loads.

## Why it matters

Infrahub syncs from the git ref of the repository,
not the working tree — uncommitted edits to Python
checks, queries, or templates are invisible to the
server after sync, so the audit consumer sees their
"fix" not take effect and assumes the platform is
broken. Bootstrap files mistakenly placed under
`objects/` are even worse: every sync re-imports
them, overwriting whatever the user typed in the
UI between syncs. Load-order mistakes show up as
`display_label` rendering `None` because the
parent reference wasn't resolved yet at the moment
the child was created.

## Checks

1. All files referenced in `.infrahub.yml` are tracked by git
2. No uncommitted changes to schema, query, Python, or template files
3. `.infrahub.yml` itself is committed
4. Bootstrap/seed data files are NOT in the `objects/`
   directory (they would be auto-imported on every sync)
5. `display_label` fields that reference parent
   relationships are flagged with a warning about
   caching during batch loading
6. Load order of object files follows dependency
   ordering (independent → types → templates →
   locations → instances → metadata)

## Common Issues

- Uncommitted Python file means Infrahub won't see the
  latest version after sync
- Bootstrap data in `objects/` causes duplicate
  creation on every repository sync
- Display labels showing `None` due to parent objects
  not yet loaded when child is created
