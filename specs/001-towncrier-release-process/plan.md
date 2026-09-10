# Implementation Plan: Towncrier-based release process

**Branch**: `001-towncrier-release-process` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-towncrier-release-process/spec.md`

> **Note on tooling**: speckit is **not installed in this repository** — there is no `.specify/` directory, so `setup-plan.sh` and the `speckit.*` commands are unavailable here. This plan follows the same template and phases as the sibling specs in infrahub-mcp and infrahub-ansible so the three stay comparable. Installing speckit here is a separate decision.

## Summary

Connect the towncrier configuration (arriving with #131) to an actual release: require a news fragment on every pull request, assemble `CHANGELOG.md` at release time, and deliver the version bump plus assembled changelog as a reviewable `chore(release)` pull request whose merge tags and publishes the release. Retire `release-drafter`.

Additionally, give the expensive eval suite a decision point it currently lacks — it is commented out in `ci.yml` and gates nothing.

## Technical Context

**Language/Version**: Python 3.13 via `uv`; workflows are GitHub Actions YAML and bash. The repo itself is Markdown skills, not application code.

**Primary Dependencies**: `towncrier` (arrives with #131); `patrickjahns/version-drafter-action@v1.3.1` (existing); `gh` CLI; `skillgrade` via the existing `skill-evals.yml`.

**Storage**: Files only — fragments in `changelog/`, assembled output in `CHANGELOG.md`.

**Testing**: No unit tests for this feature — it adds no importable code. The relevant quality signal is the eval suite, which this feature wires into CI rather than changes.

**Target Platform**: GitHub Actions (`ubuntu-latest`).

**Project Type**: Claude Code plugin distributed by tag and marketplace.

**Constraints**:

- The version lives in **five** places — `.claude-plugin/plugin.json` (canonical), `.github/.release-manifest.json`, `pyproject.toml`, every `skills/*/SKILL.md`, and `uv.lock` — reconciled by `scripts/sync-versions.sh`.
- `uv.lock` is rewritten by any `uv run`, so it drifts constantly and must travel with the release commit.
- The eval suite bills a real `ANTHROPIC_API_KEY` across 15 skills and 144 tasks, so it cannot run per-PR at full strength.
- Version computation must stay isolated in one step emitting only a version string, the seam for a later `release-prepare` migration.
- `version-sync.yml` chains off the `Auto bump version` workflow by name; renaming it would break that trigger.
- **This feature depends on #131 merging** — it supplies the towncrier config this wires up.

**Scale/Scope**: 4 workflow files, 1 deleted config, `AGENTS.md`, and `dev/guides/adding-a-skill.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

This repository has **no constitution document** and its `AGENTS.md` defines **no "Ask First" list**. The two rules it does impose:

| Rule | Applies? | Assessment |
| --- | --- | --- |
| **Rule = Test** — a new rule under `skills/*/rules/` must ship with grader + `eval.yaml` coverage | No | This feature adds no rule. It changes how evals are *invoked*, not what they assert, and leaves the matrix derived from `eval.yaml`. |
| **Versioning** — plugin.json, release-manifest, pyproject, every SKILL.md, and uv.lock must be bumped together | **Yes** | Directly in scope. The release commit now carries all five, and `release.yml` validation is extended to cover `uv.lock`, which nothing checked before. |

Generic gates: **CI/CD change** — yes, the release pipeline is replaced. **New dependency** — no; towncrier arrives with #131.

**Result: PASS.** Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-towncrier-release-process/
├── spec.md
├── plan.md              # This file
└── tasks.md
```

`research.md`, `data-model.md`, `contracts/` and `quickstart.md` are **not** generated: no unknowns to research, no data entities beyond files, and no external contract change.

### Source Code (repository root)

```text
.github/
├── release-drafter.yml              # DELETED
└── workflows/
    ├── changelog-check.yml          # NEW  — PR-time fragment gate
    ├── release-publish.yml          # NEW  — tag + publish on release-PR merge
    ├── skill-evals-scheduled.yml    # NEW  — weekly regression against main
    ├── auto-bump.yml                # EDIT — assemble changelog, open release PR,
                                     #        add uv setup, drop release-drafter.
                                     #        Workflow NAME unchanged (version-sync
                                     #        keys on it).
    ├── ci.yml                       # EDIT — enable smoke evals; add the
                                     #        release-PR regression gate
    └── release.yml                  # EDIT — validate uv.lock against the tag

AGENTS.md                            # EDIT — Changelog section
dev/guides/adding-a-skill.md         # EDIT — fragment instead of release-drafter
```

**Structure Decision**: No source-tree option applies; this feature touches no skill content. The layout above is the real set of paths changed.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
