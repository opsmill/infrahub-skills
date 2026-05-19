# PR 2: managing-transforms — union-fragments + async artifact regen

**Date:** 2026-05-19
**Branch:** `general-improvements` (continues after PR 1)
**Source:** Real-world demo session feedback (bugs 1, 7 of 7)

## Background

This is PR 2 of 4 in the managing-skills improvements arc. PR 1
(closed) covered bugs 2-5 in `managing-generators`. PR 2 covers
the two transform-layer bugs from the same demo:

- **Bug 1:** `queries/config/sdwan_edge.gql` queried
  `DcimDevice.location` as a non-union — but `location` is
  actually a union of `LocationGeneric | LocationSite |
  LocationHosting | …`, and `LocationHosting` has no `name`
  field. Result: `CoreRepository` schema-sync threw
  `Cannot query field 'name' on type 'LocationHosting'`. The
  repo never finished syncing → 0 generator definitions →
  `invoke init` timed out.
- **Bug 7:** The catalog POSTs
  `/api/artifact/generate/<def-id>?branch=<branch>` for every
  artifact definition. This endpoint is **fire-and-forget**
  (returns 200 immediately). The async server-side regen
  sometimes runs before the generator's group-membership write
  is visible on the read replica → sees zero targets → silently
  creates no artifacts. The catalog reported "success" while
  shipping nothing.

The `infrahub-managing-transforms` skill currently has rules for
type selection, Python/Jinja2 mechanics, and artifact
*configuration* — but says nothing about querying union
relationships, and nothing about the async nature of artifact
regeneration. This PR closes both gaps.

## Scope

PR 2 covers only `infrahub-managing-transforms`. PRs 3 and 4
are tracked separately:

- PR 3: cross-cutting GraphQL dry-run rule in `infrahub-common`
- PR 4: hook advisory wording

## Bug coverage

| Bug | Description | Rule |
| --- | --- | --- |
| 1 | Query field on union type (`DcimDevice.location` →   `LocationHosting` has no `name`) | rule #1 (`queries-union-fragments`) |
| 7 | Artifact regen race (`/api/artifact/generate` is fire-and-forget) | rule #2 (`artifacts-async-regen-polling`) |

## Changes

### Rule files

1. **New** `skills/infrahub-managing-transforms/rules/queries-union-fragments.md`
   (CRITICAL):
   - When a relationship's `peer:` in the schema is a **generic**
     (or a union of generics), the query must use GraphQL inline
     fragments (`... on TypeName { fields }`) to select fields
     that are specific to each concrete type.
   - Querying fields directly on the union (e.g.,
     `location { node { name { value } } }`) fails for any
     concrete type that doesn't define that field.
   - List of the most common union-typed relationships in
     Infrahub's base schema (table of `node.relationship → peer
     generic`), with the concrete types that inherit from each
     and which fields they all share vs. which are type-specific.
   - **Anti-pattern** showing the bug 1 query verbatim and the
     server error.
   - **Correct pattern** using `... on LocationSite { … } ... on
     LocationBuilding { … }` (and explicit handling for types
     with no useful field, like `LocationHosting`).
   - "How to know if a relationship is a union" — find the
     `peer:` in the schema; if it's a generic name and the
     generic has `inherit_from` consumers with diverging
     attribute sets, you need fragments.

2. **New** `skills/infrahub-managing-transforms/rules/artifacts-async-regen-polling.md`
   (HIGH):
   - `/api/artifact/generate/<def-id>?branch=<branch>` is
     fire-and-forget. The HTTP 200 means "regen request
     accepted", not "regen finished".
   - The async regen can run before a recent generator's
     group-membership write is visible on the read replica
     → race window where the regen sees the wrong group state.
   - Required pattern:
     - POST `/api/artifact/generate/...`
     - Poll `CoreArtifact` filtered by the artifact definition
       and target group
     - Wait until count matches expected OR re-POST once on
       miss
     - Hard timeout with a warning so the user sees the gap
   - Code skeleton showing a polling loop with `client.filters`,
     `asyncio.sleep`, and a timeout.
   - When this matters: any caller that triggers regen
     programmatically (catalog page, CI job, generator
     orchestration). Manual regen in the UI doesn't need this.

### Section index

3. **Edit** `skills/infrahub-managing-transforms/rules/_sections.md`
   to add the new `queries-` prefix and extend the `artifacts-`
   entry to mention async-regen polling.

### Grader infrastructure

4. **New** `graders/managing-transforms/__init__.py` (empty
   package marker).

5. **New** `graders/managing-transforms/lib.py`:
   - I/O: `load_output_gql(path)` (returns raw text — full
     GraphQL parsing not required) and `load_output_py(path)`
     (returns parsed AST tree).
   - `find_inline_fragments(gql_text) -> list[str]` — return
     all `... on <TypeName>` matches.
   - `field_appears_directly_under(gql_text, relationship,
     field) -> bool` — heuristic: does the query select
     `<field>` inside a `<relationship> { node { … }
     }` block *without* a preceding `... on` fragment? Used
     to flag the bug 1 pattern.
   - `has_post_to_artifact_generate(tree) -> bool` — AST scan
     for `httpx.post`, `requests.post`, or `client.post` calls
     whose URL string literal contains `/api/artifact/generate`.
   - `has_loop_construct(tree) -> bool` — at least one
     `ast.While` or `ast.For` exists.
   - `references_core_artifact_after_post(tree) -> bool` —
     after the regen POST, the code includes a
     `client.filters(kind="CoreArtifact", …)` or
     `client.get(kind="CoreArtifact", …)` call.
   - `CHECKS` registry; `run_checks(check_names, output_paths)`
     entry point.

6. **New** `graders/managing-transforms/check_query_union_fragments.py`
   — task grader for the union-fragments eval.

7. **New** `graders/managing-transforms/check_artifact_regen_polling.py`
   — task grader for the artifact-polling eval.

### Eval tasks (added to root `eval.yaml`)

8. **Task** `transform-query-union-fragments`
   (rule #1, deterministic grader):
   - Prompt: "Write a GraphQL query for a Jinja2 transform that
     fetches DcimDevice with the device's name, role, and its
     location's name + shortname. Note that location is a union
     of LocationSite | LocationBuilding | LocationHosting —
     LocationHosting has no name field, so handle it
     explicitly."
   - Output: `output.gql`.
   - Assertions:
     - `query-uses-inline-fragments-for-location`
     - `query-no-direct-field-on-union-location`

9. **Task** `transform-artifact-regen-polling`
   (rule #2, deterministic grader):
   - Prompt: "Write a Python helper that triggers regeneration
     for an artifact definition (POST to
     `/api/artifact/generate/<def-id>?branch=<branch>`) and
     waits for completion. Don't return success until the
     expected number of CoreArtifact instances exist for that
     definition + target group. Time out after 60 seconds with
     a warning."
   - Output: `output.py`.
   - Assertions:
     - `posts-artifact-generate-endpoint`
     - `has-polling-loop`
     - `polls-coreartifact-after-post`

### Sync + docs

10. Run `python scripts/sync-evals.py` to regenerate
    `evaluations/infrahub-managing-transforms.json` (new file,
    first evals for this skill).

11. Update `CHANGELOG.md` `[Unreleased]` section with the
    transforms additions.

## Implementation order

1. Write the two rule files + update `_sections.md`.
2. Scaffold `graders/managing-transforms/` (lib.py skeleton +
   `__init__.py`).
3. Add I/O + AST + GraphQL-text helpers to lib.py (TDD).
4. Add check functions for union-fragments (TDD).
5. Add check functions for artifact-polling (TDD).
6. Write the two task grader scripts.
7. Verify each grader locally against compliant + violating
   fixtures.
8. Add the two eval tasks to `eval.yaml`.
9. Run `python scripts/sync-evals.py`.
10. Update `CHANGELOG.md`.

## Risks and mitigations

- **GraphQL text parsing is fragile.** Using regex/text matches
  instead of a real GraphQL parser means edge cases (multi-line
  queries, comments) could trick the grader. Mitigation: the
  check only fires on simple direct-field patterns; an
  unparseable but valid query falls through to "passes."
- **Artifact polling heuristic is loose.** The three-piece
  check (POST + loop + CoreArtifact reference) can be satisfied
  by code that doesn't actually poll correctly (e.g., the loop
  is for an unrelated purpose). Mitigation: this is acceptable
  for an eval bar — the goal is to catch "the model didn't
  poll at all," not to verify polling semantics. Document the
  limitation in lib.py.
- **No GraphQL union list in schema introspection at eval
  time.** The grader can't verify which relationships are
  *actually* union-typed in the user's schema. It only checks
  for explicit `... on` syntax when `location { node { ... } }`
  appears. Mitigation: scope the eval to a known union
  relationship (`location`) and document the assumption.

## Out of scope

- PR 1 (already shipped as `general-improvements` 1-14
  commits): managing-generators rules.
- PR 3: cross-cutting GraphQL dry-run validation rule in
  `infrahub-common`.
- PR 4: hook activation wording.
- Open issues #22-29 (menu and generator concerns) — none
  addressed here.

## Acceptance

PR 2 is done when:

- Both new rule files committed under
  `skills/infrahub-managing-transforms/rules/`.
- `_sections.md` updated to register `queries-` prefix.
- `graders/managing-transforms/` exists with `lib.py` + 2
  task graders + `__init__.py`.
- `tests/graders/test_transforms_lib.py` exists with unit
  tests covering all new helpers + check functions.
- 2 new tasks added to `eval.yaml` with `trials: 3`.
- `evaluations/infrahub-managing-transforms.json` regenerated
  and committed.
- Each grader returns correct result on hand-crafted compliant
  + violating fixtures.
- Full test suite passes (existing tests not broken).
- `CHANGELOG.md` updated.
- (Skip live `skillgrade --smoke` for the same reason as PR 1
  — skillgrade CLI not installed locally.)
