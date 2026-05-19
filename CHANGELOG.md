# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### managing-generators

- New rule `python-relationship-references` covering the three
  accepted forms for relationship fields in
  `self.client.create()` (HFID dict, ID dict, SDK object) plus
  the bare-string and over-packed-list anti-patterns.
- New rule `python-multi-peer-add` explaining that
  `RelationshipManager.add()` takes one peer per call; iterate
  the peer list.
- New rule `patterns-natural-key-preflight` covering form-driven
  mutations that collide with bootstrap-seeded keys.
- New advisory rule `testing-integration` recommending
  end-to-end runs against a live instance before merge.
- Fixed misleading `device_type_id` example in `python-generate`
  that suggested bare-string relationship values.
- Added 5 deterministic evals + 4 graders to `eval.yaml` (first
  evals for this skill).

### managing-transforms

- New rule `queries-union-fragments` documenting the need for
  GraphQL inline fragments on union-typed relationships
  (`DcimDevice.location`, `Organization*` peers) to avoid
  "Cannot query field 'X' on type 'Y'" failures in
  CoreRepository schema-sync.
- New rule `artifacts-async-regen-polling` documenting that
  `POST /api/artifact/generate` is fire-and-forget and
  programmatic callers must poll `CoreArtifact` to confirm
  completion.
- Added 2 deterministic evals + graders to `eval.yaml` (first
  evals for this skill).

### Notes

- `skillgrade --smoke` was not run in this branch (skillgrade
  CLI not installed in the dev environment). Run before merging
  to baseline pass rates against the new evals.

## [1.1.0] - 2026-03-18

### Added

- 7 skills: managing-schemas, managing-objects,
  managing-checks, managing-generators,
  managing-transforms, managing-menus, auditing-repo
- Shared rules and references in skills/infrahub-common/
- Hook-based Infrahub project detection
- Metadata version tracking in SKILL.md frontmatter
- Release manifest (.github/.release-manifest.json)

### Changed

- Restructured plugin from v1 to v2 architecture
  with rule-based skills
