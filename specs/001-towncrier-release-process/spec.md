# Feature Specification: Towncrier-based release process

**Feature Branch**: `001-towncrier-release-process`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Replace the release-drafter based release process with a towncrier-managed changelog, label-driven version bumping, and a reviewable release PR, shaped to match the opsmill-cicd-workflows release-prepare contract for later migration."

## Context

Release notes here come from `release-drafter`, which lists PR titles. Readers get whatever a PR happened to be called rather than an explanation written for them.

towncrier is arriving separately in PR #131 (config, `changelog/` with the seven standard OpsMill types, template, and a seeded `CHANGELOG.md`). **This feature depends on that PR merging** and supplies the half it deliberately left out: nothing yet runs `towncrier build`, enforces a fragment, or connects the assembled changelog to a release.

This repository has an unusually wide version fan-out — `.claude-plugin/plugin.json`, `.github/.release-manifest.json`, `pyproject.toml`, every `skills/*/SKILL.md`, and `uv.lock` — reconciled by `scripts/sync-versions.sh`, with `release.yml` validating the first four against the tag. `uv.lock` is validated by nothing and reappears as a stray diff in later PRs.

It also carries an expensive quality signal the sibling repos do not: `skill-evals.yml`, with `smoke`/`reliable`/`regression` presets over 15 skills and 144 eval tasks, billed against a real API key. Today it runs only on manual dispatch, so it gates nothing.

This is the second of three sibling adoptions (infrahub-mcp pilots, then this repo, then infrahub-ansible). All three implement locally but are shaped to match the `opsmill-cicd-workflows` `release-prepare` contract, so a later migration owned by SRE is workflow rewiring rather than redesign.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A contributor's own words reach the release (Priority: P1)

A contributor changes a skill and records that change in one line, in the same pull request. When the release ships, their line appears in the release notes — nobody reconstructs it from PR titles.

**Why this priority**: This is the outcome; everything else is machinery serving it. It is also the only story that delivers value with no dependency on the release job being rebuilt.

**Independent Test**: Merge a PR carrying a fragment, cut a release, confirm the line appears verbatim in the published release body.

**Acceptance Scenarios**:

1. **Given** a contributor opens a PR changing a skill, **When** they merge it with no newsfragment and no `ci/skip-changelog` label, **Then** the PR check fails and names the fragment path to create.
2. **Given** the contributor adds `changelog/<id>.<type>.md` and merges, **When** the next release is published, **Then** the release body contains that line under its category heading.
3. **Given** a trivial PR labelled `ci/skip-changelog`, **When** it is merged with no fragment, **Then** the check passes.

---

### User Story 2 - Maintainer cuts a release from a reviewable, quality-gated PR (Priority: P2)

A maintainer promotes accumulated work. The version is computed from PR labels, `CHANGELOG.md` is assembled, and both arrive as a pull request on which the expensive `regression` eval suite runs. An admin reviews grader results alongside the changelog before merging.

**Why this priority**: Delivers the auditable release path, retires `release-drafter`, and gives the eval suite a decision point it currently lacks. User Story 1 already delivers a correct changelog without it.

**Independent Test**: Trigger release preparation, confirm a `chore(release): vX.Y.Z` PR appears carrying version files and the assembled changelog, that `regression` runs on it, and that publishing is impossible until it merges.

**Acceptance Scenarios**:

1. **Given** merged PRs labelled `changes/minor`, **When** release preparation runs, **Then** the computed version is the correct minor bump, emitted as a single version string from a discrete step.
2. **Given** fragments exist in `changelog/`, **When** the release PR is built, **Then** all five version locations carry the new version and `CHANGELOG.md` gains the assembled section.
3. **Given** the release PR exists, **When** CI runs on it, **Then** the `regression` eval preset runs and blocks merge on failure.
4. **Given** no fragments exist, **When** release preparation runs, **Then** it fails rather than producing an empty changelog section.
5. **Given** the release PR is merged and the GitHub release published, **Then** the release body is the towncrier-rendered section.

---

### User Story 3 - Curated notes for a notable release (Priority: P3)

For a release worth explaining, a maintainer produces the workflow-first prose page from the assembled changelog, published to the docs site under the existing release-notes convention.

**Why this priority**: Optional by design. `CHANGELOG.md` covers every release; this covers releases where a human has something to teach. This repo already practises it — `docs/docs/release-notes/release-X_Y_Z.mdx` with `sidebar_position: 1` and older pages shifted down.

**Independent Test**: Take a published release's changelog section, run the release-notes skill against it, confirm the page renders in the docs build with correct sidebar ordering.

**Acceptance Scenarios**:

1. **Given** a published minor release, **When** the release-notes skill runs with the towncrier output as input, **Then** a release-notes page is produced, older pages are renumbered, and the docs build passes.

---

### Edge Cases

- **Dependabot and bot PRs** cannot write fragments — they are auto-labelled `ci/skip-changelog`.
- **A release where every PR was skip-labelled** yields zero fragments: preparation hard-fails and the releaser adds a housekeeping fragment. There is no empty-release opt-out.
- **`uv.lock` drifts** because any `uv run` rewrites it and nothing validates it against the tag; the release PR must include it so it stops surfacing as stray diffs.
- **The `regression` suite fails on the release PR** — the release is blocked, not merged. Cost is incurred once per release rather than once per PR.
- **A skill is added or removed between releases** — the eval matrix is derived from `eval.yaml`, so it must pick that up without a hardcoded list.
- **Any root-level markdown change triggers a full Docusaurus build** (`documentation_all` covers `**/*.{md,mdx}`), so every fragment pays a docs-build cost.
- **Two PRs choosing the same fragment slug** collide as an ordinary file conflict, resolved in git.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fail a pull-request check when the PR adds no newsfragment and carries no `ci/skip-changelog` label.
- **FR-002**: System MUST compute the next version from PR labels (`changes/*`, `type/*`) and expose it as a single version string produced by a discrete step.
- **FR-003**: System MUST assemble `CHANGELOG.md` from newsfragments using towncrier at release time, and MUST fail rather than emit an empty section.
- **FR-004**: System MUST use the towncrier-rendered section as the GitHub Release body.
- **FR-005**: System MUST keep all five version locations in step — `.claude-plugin/plugin.json`, `.github/.release-manifest.json`, `pyproject.toml`, every `skills/*/SKILL.md`, and `uv.lock` — and MUST include `uv.lock` in the release change.
- **FR-006**: System MUST run the `smoke` eval preset on pull requests touching `skills/`.
- **FR-007**: System MUST run the `regression` eval preset on a schedule against `main`, independent of any release.
- **FR-008**: System MUST run the `regression` eval preset on the release pull request as a blocking check.
- **FR-009**: Users MUST be able to skip the fragment requirement on a trivial PR via `ci/skip-changelog`.
- **FR-010**: Release changes MUST arrive as a reviewable pull request requiring admin approval before a tag is created.
- **FR-011**: System MUST NOT retain `release-drafter` — its configuration and workflow wiring are removed.
- **FR-012**: Version computation MUST remain separable from the release job, so it can later be wired into `release-prepare` as `bump-strategy: manual` with an explicit `version:` input.
- **FR-013**: The eval matrix MUST continue to be derived from `eval.yaml` rather than a hardcoded skill list.

### Key Entities

- **Newsfragment**: `changelog/<id>.<type>.md`; one per change, one line of Markdown. Arrives with PR #131.
- **CHANGELOG.md**: the assembled canonical record; seeded by PR #131, first populated by this feature.
- **Release PR**: `chore(release): vX.Y.Z`; carries version files plus the assembled changelog, and is where the quality gate and admin approval live.
- **GitHub Release body**: the towncrier-rendered section; replaces the release-drafter PR-title list.
- **Version string**: label-derived; written to five locations and used as the `v`-prefixed git tag.
- **Eval preset**: `smoke` (per-PR), `reliable`, `regression` (scheduled and release-blocking).
- **Curated release-notes page**: `docs/docs/release-notes/release-X_Y_Z.mdx`, skill-authored, existing convention.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of releases published after adoption carry at least one human-written changelog entry.
- **SC-002**: Zero changelog merge conflicts across all pull requests in the first two release cycles.
- **SC-003**: No release requires a changelog commit after publication — notes are complete at publish time.
- **SC-004**: All five version locations report the same version at every tagged commit, `uv.lock` included.
- **SC-005**: No release ships without a passing `regression` run and a recorded admin approval.
- **SC-006**: `regression` runs at most once per release plus its scheduled cadence — per-PR spend stays at the `smoke` preset.
- **SC-007**: A later migration onto the shared workflows changes only workflow wiring — zero edits to fragment content, fragment directory, or category taxonomy.

## Governance Gates Crossed

This repository's `AGENTS.md` defines no "Ask First" list. The two rules it does impose are respected:

- **Rule = Test** — this feature adds no rule under `skills/*/rules/`, so no grader or `eval.yaml` task is required. It changes how evals are *invoked*, not what they assert.
- **Versioning** — this feature touches the documented bump procedure directly and must keep `scripts/sync-versions.sh`, `auto-bump.yml` and `release.yml` validation consistent with it, extending the list to include `uv.lock`.

Generic gates: **CI/CD change** — yes, the release pipeline is replaced. **New dependency** — no, towncrier arrives with PR #131.

## Assumptions

- PR #131 merges first; this feature depends on the towncrier configuration it adds.
- PR labels are applied reliably; conventional-commit type prefixes are **not** trustworthy in this repo — `docs:` has landed on commits that were really fixes — which is why the bump stays label-driven rather than adopting the platform's commit-driven `auto-semver`.
- A release PR is an acceptable substitute for a `develop` branch as the quality gate and admin review point. This replaces the proposal to add `develop` here, and needs the proposer's agreement.
- The single `main` branch model is retained.
- SRE owns the eventual migration onto the shared reusable workflows, on their own timeline.
- The `opsmill-cicd-workflows` `changelog-towncrier` composite currently hard-codes a `changes/` directory and will need to honour towncrier's configured `directory` before migration; tracked separately against that repository.

## Out of Scope

- Migrating onto the shared reusable workflows in `opsmill-cicd-workflows`.
- Installing speckit in this repository — this spec is written to the shared template without it.
- Introducing a `develop` branch.
- Changing what the eval suite asserts, or adding new graders and rules.
- Unifying conventional-commit types with towncrier fragment types — they answer different questions and both remain.
