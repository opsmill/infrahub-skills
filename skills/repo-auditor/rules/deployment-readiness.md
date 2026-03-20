# Rule: deployment-readiness

**Severity**: MEDIUM
**Category**: Deployment

## What It Checks

Validates the repository is ready for deployment to Infrahub.

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
