# feat(adapters): add a ServiceNow CMDB source adapter

Adds `servicenow`, a source adapter that reads network gear and locations from the Table API.

## Checks run

- `uv run invoke format`
- `uv run invoke lint` (no new pylint findings on the new files)
- `uv run ty check .`
- `uv run invoke tests.tests-unit` (the new tests ran: 42 passed, none skipped)
- `uv run rumdl check .`
- `infrahub-sync list --directory examples/`
- `infrahub-sync generate --name from-servicenow --directory examples/`
- `infrahub-sync diff --name from-servicenow --directory examples/`
- Docs page `docs/docs/adapters/servicenow.mdx`, entry in `docs/sidebars.ts`, row in `docs/docs/adapters/choosing-an-adapter.mdx`
- Spec documents re-read against the code: `dev/specs/017-servicenow-adapter/spec.md`, `plan.md`, `tasks.md`
