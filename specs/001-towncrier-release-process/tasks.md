---
description: "Task list for the towncrier-based release process"
---

# Tasks: Towncrier-based release process

**Input**: Design documents from `/specs/001-towncrier-release-process/`

**Prerequisites**: [spec.md](./spec.md), [plan.md](./plan.md), and **PR #131 merged** (supplies the towncrier configuration).

**Tests**: No test tasks — the feature adds no importable code. The relevant quality signal is the eval suite, which Phase 4 wires into CI.

**Organization**: Grouped by the user stories in spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task serves

## Phase 1: User Story 1 — A contributor's own words reach the release (P1)

**Goal**: A pull request that changes behaviour cannot merge without a news fragment.

**Independent test**: Open a PR with no fragment → the check fails; add one → it passes; label `ci/skip-changelog` with no fragment → it passes.

- [x] T001 [US1] Add `.github/workflows/changelog-check.yml`, failing a pull request that adds no file under `changelog/` unless it carries `ci/skip-changelog`. Query the API via `gh pr view --json files` rather than diffing locally, so the result does not depend on checkout depth.
- [x] T002 [US1] Make the failure message actionable — name the `towncrier create` command, the seven types, and the escape-hatch label.

**Checkpoint**: US1 delivers a correct changelog on its own.

---

## Phase 2: User Story 2 — Maintainer cuts a release from a reviewable PR (P2)

**Goal**: The version bump and assembled changelog arrive as a pull request; merging it publishes the release.

- [x] T003 [US2] Add `astral-sh/setup-uv` to the bump job — it had no Python tooling, so `uv run towncrier` would have failed.
- [x] T004 [US2] Keep version computation in its own step whose only output is a version string (the seam for `release-prepare`'s `bump-strategy: manual`).
- [x] T005 [US2] Add a changelog-assembly step that hard-fails when `changelog/` holds no fragments, then runs `towncrier build --version "$VERSION" --yes`.
- [x] T006 [US2] Replace the direct `main` push with a step that creates `release/v<version>`, commits all five version locations plus `CHANGELOG.md` and the consumed `changelog/`, and opens the release pull request. Re-running refreshes the same branch instead of opening a second PR.
- [x] T007 [US2] Include `uv.lock` in the release commit — any `uv run` rewrites it, so it otherwise resurfaces as a stray diff in the next unrelated PR.
- [x] T008 [US2] Add `.github/workflows/release-publish.yml`, tagging and publishing on merge with the assembled section as the body. Key the decision off *"does a tag exist for the version in `plugin.json`?"* rather than the commit message, so squash, rebase and merge behave identically.
- [x] T009 [US2] Guard the extracted body: fail if empty, and fail if it does not mention the version being released.
- [x] T010 [US2] Remove `release-drafter` — delete `.github/release-drafter.yml` and the `release-draft` job.
- [x] T011 [US2] Leave the `Auto bump version` workflow **name** unchanged so `version-sync.yml`'s `workflow_run` trigger keeps matching.
- [x] T012 [US2] Extend `release.yml` to validate `uv.lock` against the tag. It already validated plugin.json, the release manifest, pyproject and every SKILL.md — `uv.lock` was the one location nothing checked, which is what SC-004 requires.

**Checkpoint**: Releases are auditable and every version location is validated.

---

## Phase 3: Eval gating (supports US2)

**Goal**: Turn the eval suite from a manual dispatch into a tiered gate, without paying full price per pull request.

- [x] T013 Enable `smoke` evals on pull requests touching `skills/` — the job existed in `ci.yml` but was commented out, so it gated nothing.
- [x] T014 Add `.github/workflows/skill-evals-scheduled.yml` running the full `regression` preset weekly against `main`, so regressions surface continuously rather than under release pressure.
- [x] T015 Run `regression` on the release pull request as the release gate, keyed on `startsWith(github.head_ref, 'release/')`.
- [x] T016 Keep the eval matrix derived from `eval.yaml` rather than a hardcoded skill list, so adding or removing a skill needs no workflow edit.
- [ ] T017 **Repository setting, not a file**: add `skill-evals-regression` to `main`'s required status checks. Until then the job *runs* on the release PR but does not *block* it — `main` currently requires 1 approving review and **0 status checks**.

---

## Phase 4: Verification

- [x] T018 Exercise `towncrier build --version 1.2.9`; confirm both pending fragments assemble under the right heading.
- [x] T019 Exercise the release-body extraction; confirm it returns exactly the new section and that the version guard trips when it should.
- [x] T020 Verify the `uv.lock` version extraction returns the project version (`1.2.8`) rather than a dependency's.
- [x] T021 Revert the simulation so no assembled changelog or consumed fragment is committed.
- [x] T022 [P] `yamllint` across `.github/workflows/`.
- [x] T023 [P] `rumdl check .` across the repository — this caught a dangling link in `dev/guides/adding-a-skill.md` to the deleted release-drafter config.
- [ ] T024 **Cannot be done pre-merge**: `auto-bump.yml` and `release-publish.yml` only trigger on `main`, so the release path gets its first real exercise on the next release. Watch that run.

---

## Phase 5: Documentation

- [x] T025 [P] Add the Changelog section to `AGENTS.md`, including the eval tiering and the rule that versions are never bumped by hand.
- [x] T026 [P] Replace the release-drafter passage in `dev/guides/adding-a-skill.md` with the fragment workflow, and correct what the `changes/*` label does — it drives the version bump, not a release-notes category.
- [x] T027 Add a news fragment for this change itself, exercising the workflow it introduces.

---

## Dependencies

- **PR #131 → everything**: the towncrier configuration must exist first.
- **Phase 1 is independent of Phase 2**: US1 ships value alone.
- **T010 → T026**: deleting release-drafter breaks the doc link, so both must land together.
- **T015 → T017**: the job must exist before it can be made a required check.

## Deferred

- **US3 (curated release notes)** is not implemented. The existing `docs/docs/release-notes/*.mdx` practice continues by hand for notable releases.
- **T017 and the `develop`-branch question** need a human: the required-check setting, and the proposer's agreement that a release PR replaces his `develop` proposal.
