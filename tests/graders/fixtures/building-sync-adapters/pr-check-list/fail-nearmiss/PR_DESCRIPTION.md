# feat(adapters): add a ServiceNow CMDB source adapter

Adds `servicenow`, a source adapter that reads network gear and locations from the Table API.

## Checks run

- `uv run invoke format`: no changes
- `uv run invoke lint`: no new pylint findings on the new files
- `uv run ty check .`: passed
- `uv run invoke tests.tests-unit`: passed; the new tests ran: 42 passed, none skipped
- `uv run rumdl check .`: passed
- `uv run invoke docs.docusaurus`: built
- `infrahub-sync list --directory examples/`: lists the examples
- `infrahub-sync generate --name from-netbox --directory examples/netbox_to_infrahub/`: passed
- `infrahub-sync diff --name from-netbox --directory examples/netbox_to_infrahub/`: no changes
- News fragment: `changelog/412.added.md`
- Docs page `docs/docs/adapters/servicenow.mdx`, entry in `docs/sidebars.ts`, row in `docs/docs/adapters/choosing-an-adapter.mdx`, one line each in `docs/docs/readme.mdx`, `README.md` and `AGENTS.md`
- Spec documents re-read against the code: `dev/specs/017-servicenow-adapter/spec.md`, `plan.md`, `tasks.md`
