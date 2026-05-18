# PR 1: managing-generators — integration-layer rules + evals

**Date:** 2026-05-18
**Branch:** `general-improvements`
**Source:** Real-world demo session feedback (7 bugs across one
Infrahub demo build, mapped to skill gaps)

## Background

Pete ran a multi-day session building an Infrahub SDWAN demo and
hit seven bugs that cost significant time. Four of them — bugs
2, 3, 4, and 5 in his debrief — live at the
`client.create` / `RelationshipManager` API surface. That is the
*integration layer* between what the model assumes about
Infrahub's SDK and what the server actually accepts.

The `infrahub-managing-generators` skill currently covers
schema-layer concerns (architecture, idempotency, tracking) well,
but is thin on integration-layer detail. Worse, the existing
`python-generate.md` example uses misleading shorthand
(`'Use ID for relationships'`, `device_type_id` as a singular
variable with no shape hint) that directly contributed to bug 3.

This PR closes that gap with four new rules, one rule edit, and
five eval tasks gated by AST-based deterministic graders.

## Scope

This PR scopes only `infrahub-managing-generators`. PRs 2-4
(managing-transforms, infrahub-common, hook activation) are
tracked separately.

## Bug coverage

| Bug | Description | Rule covering it |
| --- | --- | --- |
| 2 | Composite HFID over-packed for single-component target | rule #2 (`python-relationship-references`) |
| 3 | Bare string interpreted as `id` lookup | rule #2 + rule #1 edit |
| 4 | List passed to `RelationshipManager.add` instead of iterating | rule #3 (`python-multi-peer-add`) |
| 5 | `IpamPrefix` uniqueness collision on bootstrap-seeded key | rule #4 (`patterns-natural-key-preflight`) |
| Cross-cutting | "Run generator end-to-end before merge" | rule #5 (`testing-integration`) |

## Changes

### Rule files

1. **Edit** `skills/infrahub-managing-generators/rules/python-generate.md`:
   - Replace the misleading `device_type_id` example with explicit
     `{"hfid": ["<name>"]}` form.
   - Remove the standalone comment `# Use ID for relationships`.
   - Add a cross-reference pointer to new rule #2.

2. **New** `skills/infrahub-managing-generators/rules/python-relationship-references.md`
   (CRITICAL):
   - The three accepted forms for relationship fields in
     `client.create`:
     - **HFID lookup (single-component):**
       `{"hfid": ["<name>"]}`
     - **HFID lookup (composite):**
       `{"hfid": ["<part-a>", "<part-b>"]}` — list length must
       match the schema's `human_friendly_id` declaration
     - **Explicit ID:** `{"id": "<uuid>"}`
     - **SDK object reference:** pass a variable holding a node
       previously returned by `client.get` or `client.create`
   - **WARNING block:** a bare string for a relationship field is
     interpreted as `{"id": "<string>"}` — never HFID lookup. The
     server returns "Unable to find the node" because the string
     is not a valid UUID.
   - **WARNING block:** over-packing the HFID list (e.g. passing
     `["name", "manufacturer_name"]` for a single-component HFID)
     fails. Inspect the schema's `human_friendly_id` value before
     constructing the list.
   - Cross-link to
     `infrahub-managing-schemas/rules/display-human-friendly-id`.

3. **New** `skills/infrahub-managing-generators/rules/python-multi-peer-add.md`
   (HIGH):
   - `RelationshipManager.add()` takes one peer per call.
   - Passing a list literal (`group.members.add([p1, p2, p3])`)
     creates ONE peer with a composite HFID equal to the list
     contents. The resulting mutation looks like
     `members: [{hfid: [<peer1>, <peer2>, <peer3>]}]` — wrong.
   - Pattern: iterate the peer collection, call `.add(p)` once
     per peer, then `.save()` once at the end.
   - Same constraint applies to other RelationshipManager
     mutators (`.update`, `.remove`).

4. **New** `skills/infrahub-managing-generators/rules/patterns-natural-key-preflight.md`
   (MEDIUM):
   - When mutations are driven by user input (forms, catalogs,
     ad-hoc scripts) and bootstrap data may have already seeded
     the natural key, pre-flight check before creating.
   - **Pattern A — pre-flight check** (`client.get` + branch on
     `NodeNotFound`): use when the desired behavior is "fail
     loudly with a friendly message if the object already
     exists."
   - **Pattern B — upsert** (`save(allow_upsert=True)`): use when
     the desired behavior is "create or update silently." This
     is the default in `InfrahubGenerator.generate()`.
   - **Anti-pattern:** `client.create` followed by `.save()` with
     no upsert and no preflight → raw server-side
     `UniquenessConstraintError` reaches the user.
   - Code skeletons for both patterns.

5. **New** `skills/infrahub-managing-generators/rules/testing-integration.md`
   (LOW, advisory):
   - After implementing a generator, run it end-to-end against a
     live Infrahub instance before declaring done.
   - Unit tests on the input dict do not cover SDK call shape —
     bugs 2, 3, and 4 all type-check and pass unit tests but
     fail at runtime against the real server.
   - Concrete workflow: `infrahubctl generator list` →
     `infrahubctl generator run <name> <param>` → verify created
     objects exist in the UI or via GraphQL.
   - Same workflow applies during PR review on a branch.

6. **Edit** `skills/infrahub-managing-generators/rules/_sections.md`:
   - Note `python-` now includes relationship-references and
     multi-peer-add.
   - Note `patterns-` now includes natural-key-preflight.
   - Note `testing-` now includes integration.

### Grader infrastructure

7. **New** `graders/managing-generators/lib.py`:
   - `load_output_py(path)` — parse a Python file via `ast`,
     return module tree. Returns `(None, "")` on parse failure.
   - `find_client_create_calls(tree)` — yield each
     `await self.client.create(...)` call with parsed `kind`
     string and the `data` dict literal as a Python dict (only
     literal-resolvable values; opaque expressions are kept as
     `ast` nodes).
   - `find_relationship_manager_add_calls(tree)` — yield each
     `.add(...)` call on attribute chains ending in `members`,
     `peers`, or any attribute, with the argument's ast node.
   - `is_hfid_dict_literal(node)` —
     `{"hfid": [<literal strings>]}` check.
   - `is_bare_string_literal(node)` — `ast.Constant(value=str)`.
   - `CHECKS` registry mapping assertion names to check
     functions returning `(bool, str)`.
   - `run_checks(checks, paths)` — return skillgrade JSON
     (`{"score": float, "details": str, "checks": [...]}`).

8. **New** `graders/managing-generators/check_relationship_hfid_encoding.py`
   — task 1 grader.

9. **New** `graders/managing-generators/check_relationship_three_forms.py`
   — task 2 grader.

10. **New** `graders/managing-generators/check_multi_peer_iteration.py`
    — task 3 grader.

11. **New** `graders/managing-generators/check_natural_key_preflight.py`
    — task 4 grader.

### Eval tasks (added to root `eval.yaml`)

12. **Task** `generator-relationship-hfid-encoding` (rule #2):
    - Prompt: build a POP topology generator that creates
      DcimDevice instances referencing `device_type` and
      `manufacturer` by HFID. Both are single-component HFIDs.
    - Assertions: `relationship-hfid-form-correct`,
      `no-bare-string-relationship`, `no-overpacked-hfid-list`.

13. **Task** `generator-relationship-three-forms` (rule #2):
    - Prompt: generator references nodes by all three forms
      (HFID, SDK object from earlier `client.get`, explicit ID
      from a query result). Forces the model to exercise the
      full reference matrix.
    - Assertions: `hfid-form-for-name-lookup`,
      `sdk-object-reference-used`, `id-form-for-uuid`.

14. **Task** `generator-multi-peer-iteration` (rule #3):
    - Prompt: generator creates a `CoreStandardGroup` and adds 5
      devices to its `members`.
    - Assertions: `members-add-iterates`,
      `no-list-passed-to-add`.

15. **Task** `generator-natural-key-preflight` (rule #4):
    - Prompt: write a script that creates an `IpamPrefix`
      `10.250.10.0/24` from user input. The prefix may already
      exist from bootstrap data; handle the collision
      gracefully.
    - Assertions: `preflight-or-upsert`,
      `no-raw-create-without-handler`.

16. **Task** `generator-process-integration-test` (rule #5,
    advisory):
    - Prompt: standard generator request, plus "explain how to
      test this end-to-end."
    - **Expectations-only** (no grader). Reviewer checks that
      the response mentions `infrahubctl generator run` against
      a live instance, and that input-dict unit tests are
      insufficient.

### Sync + docs

17. Run `python scripts/sync-evals.py` to regenerate
    `evaluations/managing-generators.json`. Commit alongside the
    `eval.yaml` change.

18. Update `CHANGELOG.md` with a bulleted list of the rule
    additions under the next version section.

19. **Do not** bump skill version in this PR. Version bumps are
    handled by the release workflow.

## Implementation order

1. Write 4 new rule files + edit `python-generate.md` +
   update `_sections.md`.
2. Build `graders/managing-generators/lib.py` with AST helpers
   and `CHECKS` registry.
3. Write 4 grader scripts.
4. Add 5 eval tasks to `eval.yaml`.
5. Run `python scripts/sync-evals.py`.
6. Verify each grader locally against hand-crafted compliant +
   violating Python fixtures. A grader that returns `pass: true`
   on a violating fixture is broken — fix before relying on
   smoke.
7. Run `skillgrade --smoke`. If any rule fails reliably (model
   ignores the prose), iterate on the rule:
   - Strengthen the WARNING block.
   - Add a concrete example of the failure mode.
   - Cross-check the description in SKILL.md for activation
     hints.
8. Update `CHANGELOG.md`.
9. Open **draft** PR (per global instruction; pass `--draft`).

## Risks and mitigations

- **AST grading complexity.** Existing graders parse YAML; this
  PR introduces Python AST parsing. Mitigation: build `lib.py`
  helpers carefully, hand-craft fixtures, run graders standalone
  before trusting smoke.
- **Rule prose may not be strong enough.** Smoke may reveal that
  the model still bare-strings relationships despite the new
  rule. Mitigation: iterate on the rule prose, especially the
  WARNING/example pairing.
- **CI matrix coverage.** This adds the first eval tasks for
  `infrahub-managing-generators`. CI may need a config check to
  confirm the matrix covers managing-generators. Investigate
  before final push.
- **AST literal resolution.** `data={"name": var}` cannot be
  fully resolved from AST alone (the value is a variable). The
  graders should:
  - Always fail if a relationship field is a bare string literal
    (`ast.Constant(value=str)`) — this is the bug 3 pattern.
  - Always fail if a relationship field is an over-packed list
    literal for a single-component HFID.
  - Treat opaque expressions (variable refs, function calls) as
    "indeterminate" / pass — they may be valid SDK objects.
  - Document this limitation in `lib.py`.

## Out of scope

- PR 2 (managing-transforms) — bugs 1 + 7
- PR 3 (infrahub-common) — pre-merge GraphQL dry-run rule
- PR 4 (hook) — stronger advisory activation wording
- Open issues #22-25 (menu skill bugs) and #26-29 (other
  generator concerns) — none are addressed by this PR

## Acceptance

PR 1 is done when:

- All 4 new rule files + edited `python-generate.md` + updated
  `_sections.md` are committed.
- `graders/managing-generators/` exists with `lib.py` + 4 task
  graders.
- 5 new tasks are added to `eval.yaml`.
- `evaluations/managing-generators.json` is regenerated and
  committed.
- Each grader returns the correct result on hand-crafted
  fixtures (compliant + violating).
- `skillgrade --smoke` runs without crashing. (Pass rate goals
  set after first smoke baseline.)
- `CHANGELOG.md` updated.
- Draft PR opened and self-reviewed.
