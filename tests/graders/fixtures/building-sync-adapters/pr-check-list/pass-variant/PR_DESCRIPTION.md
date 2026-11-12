# ServiceNow source adapter

## Summary

New source adapter for the ServiceNow Table API.

## Verification

| Check | Command | Result |
| --- | --- | --- |
| Formatting | `uv run invoke format` | clean |
| Lint | `uv run invoke lint` | clean |
| Types | `uv run ty check .` | clean |
| Unit tests | `uv run pytest tests/unit/adapters/test_servicenow.py -v` | 42 passed |
| Markdown | `uv run rumdl check .` | clean |
| Docs build | `cd docs && npm run build` | built |
| Example | `infrahub-sync generate --name from-servicenow --directory examples/` then `infrahub-sync diff --name from-servicenow --directory examples/` | 9 creates |
| Changelog | `changelog/412.added.md` | added |
| Sidebar | `docs/sidebars.ts` | entry added |
| Spec | `dev/specs/017-servicenow-adapter/tasks.md` | matches the code |
