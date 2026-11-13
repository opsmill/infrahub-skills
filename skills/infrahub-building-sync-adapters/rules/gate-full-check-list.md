---
title: Run and List Every Repository Check in the Pull Request
impact: HIGH
description: >-
  Before push and pull request, run the full infrahub-sync check list (format,
  lint, ty, unit tests that actually ran, rumdl, docs build, infrahub-sync
  list/generate/diff on the example, news fragment, docs page with sidebar and
  adapter-list entries, spec documents matched to the code) and list each one
  with its result under a checks heading in the PR description.
tags: gate, checks, pull-request, changelog, docs, ci
---

## Run and List Every Repository Check in the Pull Request

Before the push, run every check below in the
infrahub-sync checkout. The pull request description has
a checks section (a heading such as `## Checks run`)
that names each check as a command or a path, with its
result.

### Why it matters

"Lint and pytest pass" covers a third of what reviewers
check. In both adapters this skill comes from, the rest
was found late:

- **Microsoft Graph.** Pylint findings, Vale spelling
  exceptions, the docs build and the news fragment were
  found after the code was done.
- **Webex.** `plan.md`, `data-model.md`, `quickstart.md`
  and `tasks.md` in the spec directory still described
  the example the code no longer had.

CI does not close the gap. `main` declares no extras for
vendor SDKs, so tests behind `pytest.importorskip` are
skipped in CI while CI passes. Only a local run that
shows the new tests passing, not skipped, proves they
ran.

### The check list

Run from the infrahub-sync checkout:

```bash
uv run invoke format
uv run invoke lint
uv run ty check .
uv run invoke tests.tests-unit
uv run pytest -q -rs tests/adapters/test_<name>*.py
uv run rumdl check .
uv run invoke docs.docusaurus
uv run infrahub-sync list --directory examples/
uv run infrahub-sync generate --name <example-name> --directory examples/<example-dir>/
uv run infrahub-sync diff --name <example-name> --directory examples/<example-dir>/
uv run --extra dev towncrier create -c "Add a <System> source adapter." <PR>.added.md
```

- **`uv run invoke lint`** runs pylint, which already
  reports findings on unchanged code on `main`. Compare
  with the base commit and report zero new findings in
  the new files.
- **Unit tests**: the `-rs` run lists skipped tests.
  Report how many of the new tests passed and that none
  were skipped.
- **`uv run invoke docs.docusaurus`** needs
  `pnpm install` in `docs/` once.
- **`infrahub-sync diff`** needs the live systems. It
  only reads.
- **News fragment**: `changelog/<PR>.added.md`.
- **Docs**: the page `docs/docs/adapters/<name>.mdx`, its
  entry in `docs/sidebars.ts`, and its row in
  `docs/docs/adapters/choosing-an-adapter.mdx`. Add
  product names Vale rejects to
  `.vale/styles/spelling-exceptions.txt`.
- **Spec documents**: re-read every file under
  `dev/specs/<NNN>-<name>/` (or `specs/`) against the
  code, and mark each numbered requirement met, partly
  met or not met.
- **Scope**: the check in
  [scope-adapter-files-only.md](./scope-adapter-files-only.md)
  prints nothing.

Write every item as the command you ran or the path you
changed, in backticks, followed by its result. That holds
for an item not run or not done yet too: write
`` `docs/sidebars.ts`: not added yet ``, not "sidebar
pending". A reviewer can rerun a command and open a
path; a bare word gives them nothing to check.

Show the user the description before pushing: it is
approval point 5.

### Correct

```markdown
## Checks run

- `uv run invoke format`: no changes
- `uv run invoke lint`: no new pylint findings in the new files
- `uv run ty check .`: passed
- `uv run invoke tests.tests-unit`: passed; `uv run pytest -q -rs tests/adapters/test_netinventory*.py`: 38 passed, 0 skipped
- `uv run rumdl check .`: passed
- `uv run invoke docs.docusaurus`: built
- `infrahub-sync list --directory examples/`, `infrahub-sync generate --name from-netinventory --directory examples/netinventory_to_infrahub/` and `infrahub-sync diff --name from-netinventory --directory examples/netinventory_to_infrahub/`: passed
- News fragment: `changelog/415.added.md`
- Docs: `docs/docs/adapters/netinventory.mdx`, entry in `docs/sidebars.ts`, row in `docs/docs/adapters/choosing-an-adapter.mdx`
- Spec documents re-read against the code: `dev/specs/018-netinventory-adapter/spec.md`, `plan.md`, `data-model.md`, `quickstart.md`, `tasks.md`
```

### Incorrect

```markdown
## Testing

Lint and pytest pass locally.
```

### Common mistakes

- **Trusting a green CI** for an adapter whose tests are
  skipped there.
- **Leaving out the docs build and the news fragment**,
  the two items found last on the Graph adapter.
- **Not re-reading the spec documents** after the
  example or the scope changed.
- **Listing a check without running it.** Write the
  result next to each command.

Reference: [infrahub-sync repository](https://github.com/opsmill/infrahub-sync)
