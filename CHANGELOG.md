# Infrahub Skills Changelog

This is the changelog for Infrahub Skills.
All notable changes to this project will be documented in this file.

Issue tracking is located in [GitHub](https://github.com/opsmill/infrahub-skills/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub-skills/tree/main/changelog/>.

<!-- towncrier release notes start -->

## [Infrahub Skills - v1.3.0](https://github.com/opsmill/infrahub-skills/tree/v1.3.0) - 2026-09-23

### Fixed

- Menu skill no longer recreates the IPAM section Infrahub already ships, and documents attaching to a built-in section with parent: BuiltinIPAM. ([#24](https://github.com/opsmill/infrahub-skills/issues/24))
- `schema.graphql` is now documented as `infrahubctl graphql export-schema` output that is re-exported rather than hand-edited. ([#29](https://github.com/opsmill/infrahub-skills/issues/29))
- `infrahub-managing-generators` now fires on modification and debugging work, not only on
  creating a generator, and states that tracking covers every `save()` reachable from
  `generate()` including saves inside imported helpers. A generator whose own file opted out
  of tracking correctly still deleted a leaf port, because a shared addressing helper saved
  with the default. ([#78](https://github.com/opsmill/infrahub-skills/issues/78))
- `infrahub-managing-generators` now teaches `node.add_relationships()` for peers on a node
  several generator runs can write at once. The previous `.add()` plus `.save()` pattern is a
  client-side read-modify-write: `save()` sends the whole peer list, so a concurrent run
  overwrites peers another run just added. Measured at three of eight peers surviving. ([#86](https://github.com/opsmill/infrahub-skills/issues/86))
- managing-transforms: artifact regen polling now waits for each artifact's body to be retrievable (status Ready, or a present storage_id) rather than for the CoreArtifact node to merely exist. A count-only poll returned artifacts whose content fetch still 404'd. ([#88](https://github.com/opsmill/infrahub-skills/issues/88))
- The `.infrahub.yml` reference in `infrahub-common` now documents the `graphql_fragments` section, which it previously omitted from a block headed "Complete Structure", and the audit skill no longer flags that key as unrecognized. A test reads the section list from the SDK's repository config model rather than a pinned copy, so a section added upstream fails the suite once the SDK is updated instead of going missing silently. ([#122](https://github.com/opsmill/infrahub-skills/issues/122))
- The `infrahub-managing-checks`, `infrahub-managing-menus`, `infrahub-managing-objects`,
  `infrahub-managing-transforms` and `infrahub-managing-schemas` skills now fire on modifying,
  debugging and extending an existing artifact, not only on creating one. `infrahub-importing-data`
  and `infrahub-converting-netbox-device-types` gained the same triggers, and the mirror surfaces for
  `infrahub-managing-generators` were brought in line with the description it gained in #144 (unreleased). ([#143](https://github.com/opsmill/infrahub-skills/issues/143))
- `infrahub-managing-generators` now teaches the ordering between detaching a relationship and
  deleting its peers. Deleting a peer through its own `.delete()` leaves it in the holder's
  in-memory relationship manager, so a later `save(allow_upsert=True)` re-sends the deleted id.
  The rule scopes this to a hydrated relationship, names what actually hydrates one
  (`include=["<rel>"]`, not `prefetch_relationships=True`), and points at the cheapest fix:
  do not hydrate the relationship on the handle you save. ([#147](https://github.com/opsmill/infrahub-skills/issues/147))

### Housekeeping

- Added .agents and .codex routing directories so non-Claude agents find the shipped skills, contributor skills, and rules.
- Added a four-skill, three-stage contributor pipeline for skill changes: analyze a bug or grill an idea, write the failing eval or pytest, then implement and ship it, with a minimum-change ladder that keeps the repository from accreting.
- Assemble release notes with towncrier instead of release-drafter: pull requests now require a news fragment, releases arrive as a reviewable pull request gated by the regression eval suite, and the assembled changelog becomes the GitHub Release body.
- Correct the eval discrimination proof: commenting out the `Read the skill at ...` line removes the pointer, not the skill, so a 1.0 is not a verdict. Add the three readings of a 1.0 and the release-notes rung to the ground truth ladder.
- Harvested five recurring review lessons into the contributor guidance: rank evidence instead of listing phrasings when grading prose, move the rule (not the grader) when the two disagree, keep the skill's worked example out of its eval prompt, state triggers rather than a workflow summary in a description, and gate an unreleased command on a minimum version.
- Manage the changelog with [towncrier](https://towncrier.readthedocs.io/) news fragments, matching the setup used across the Infrahub repositories.
- Moved the contributor skills out of `.claude/skills/` to `.agents/skills/`, making `.agents/` the source of truth for everything this repo authors for its own agents. `.claude/` and `.codex/` now hold nothing but relative symlinks into `.agents/`, which is the canonical adapter shape. The shipped `skills/` stay at the repo root as the product: `plugin.json` exposes them and `eval.yaml` now reads them directly rather than through a routing symlink. Eight routing links become five, and `scripts/check-symlinks.py` checks them and asserts the link targets are real directories rather than links themselves.
- Replaced the leftover release-drafter guidance in the contributor docs with the towncrier news-fragment workflow.
- Rule authoring now asks how often a failure was seen, and requires the eval prompt to use a different scenario than the incident that motivated the rule.
- Stopped running the `smoke` eval preset on every pull request touching `skills/`. The suite bills a real API key, so it is now dispatch-only; the weekly `regression` run and the release-PR gate are unchanged.
- The skill-change pipeline now assesses which documentation a change leaves stale, carries the answer in the handoff, and updates those pages in the same change.
