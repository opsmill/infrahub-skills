# AGENTS.md

This file is a router for AI coding assistants working with this repository: it carries the repo-wide facts and points at [`dev/`](dev/README.md) for depth.

## Repository Overview

This is a Claude Code plugin for [Infrahub](https://github.com/opsmill/infrahub), the infrastructure data management platform by OpsMill. The plugin provides skills covering the full Infrahub development lifecycle: schema design, data population, validation checks, generators, transforms, menu customization, and live data analysis.

The skills themselves are Markdown: each one is a directory under `skills/` holding rules, examples, and reference documentation, in the [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) format. The machinery around them is Python — graders under `graders/`, the test suite under `tests/`, the gate scripts under `scripts/`, and a few bundled skill scripts — and CI runs `ruff` and `pytest` over all of it. Treat a change to that half as code, not documentation.

## Navigation

| Question | Location |
| -------- | -------- |
| How does the plugin work? | [dev/knowledges/](dev/knowledges/) |
| How do I do X? | [dev/guides/](dev/guides/) |
| How should I write skill prose? | [dev/knowledges/skill-writing-guide.md](dev/knowledges/skill-writing-guide.md) |
| What was this change meant to do? | [dev/specs/](dev/specs/) |
| What rules apply to the file I am editing? | [dev/guidelines/](dev/guidelines/) |
| What commands are available? | [§ Commands](#commands) |
| Where do AI command definitions live? | [dev/commands/](dev/commands/) |
| How do I turn PR review feedback into rules? | [.agents/skills/harvesting-skill-review/](.agents/skills/harvesting-skill-review/) |
| How do I fix a bug or add a rule in this repo? | [.agents/skills/](.agents/skills/) — `analyzing-skill-bugs` or `grilling-skill-features`, then `test-driving-skill-changes` and `implementing-skill-changes` |

Index of the whole tree: [dev/README.md](dev/README.md).

## Project Structure

Read [dev/knowledges/architecture.md](dev/knowledges/architecture.md) for the component architecture, the progressive-disclosure model, the rule/eval systems, and the design decisions behind them.

## Getting Started

Read [dev/guides/getting-started.md](dev/guides/getting-started.md) for installation options, the typical workflow, and verification steps.

## Development Guides

Read the guide that matches the task before starting work:

- [dev/guides/adding-a-skill.md](dev/guides/adding-a-skill.md) — creating a new skill (anatomy, SKILL.md, rules, evals, registration)
- [dev/guides/adding-a-rule.md](dev/guides/adding-a-rule.md) — adding or tightening a rule; required reading for the Rule = Test workflow below
- [dev/guides/running-evals.md](dev/guides/running-evals.md) — running skillgrade evals, writing graders and eval prompts

## Domain Knowledge

- [dev/knowledges/skill-writing-guide.md](dev/knowledges/skill-writing-guide.md) — how to write effective skills: descriptions, rule structure, examples, common pitfalls
- [dev/knowledges/infrahub-concepts.md](dev/knowledges/infrahub-concepts.md) — Infrahub concepts skill authors need: schema, relationships, metadata, proposed changes

## AI Command Definitions

AI command definitions live in [dev/commands/](dev/commands/).

## Commands

| Task | Command |
| ---- | ------- |
| One eval | `skillgrade --eval=<task-name> --trials=1` |
| Whole eval suite | `skillgrade --smoke` (expensive, opt in) |
| Full test suite | `uv run invoke test` |
| One test | `uv run --group test pytest tests/graders/test_common_lib.py -v` |
| Lint everything | `uv run invoke lint` |
| Fix markdown formatting | `uv run invoke format` |
| Regenerate the JSON evals | `uv run python scripts/sync-evals.py` |
| Check the installed plugin against this tree | `uv run invoke freshness` |

`uv run invoke lint` runs rumdl, yamllint, and
`scripts/check-cli-invocations.py`. CI runs those three plus `ruff`,
`pytest`, and `scripts/check-symlinks.py`.

The single-eval line is the one that matters for cost. A full
`skillgrade --smoke` run is the expensive default people reach for out of
habit; `--eval=<task> --trials=1` answers "does this one rule work" for a
fraction of it, and that is the question nearly every change asks.

## Boundaries

- Never weaken a grader check, drop a fixture, or loosen an eval prompt to
  make a change pass. That is the local form of rewriting a test to go
  green, and it is worse here because it looks like progress.
- Never report an interrupted or timed-out `skillgrade` run as a pass.
- If a command fails, report the failure. Do not present an assumption as a
  confirmed result.
- Do not widen scope beyond what the task asked for.
- Never commit a `.skill-change-*.md` handoff file or a `*-workspace/`
  eval directory.

## Rules

Path-scoped rules live in [dev/guidelines/](dev/guidelines/), which `.claude/rules` symlinks to. Each declares the globs it applies to in frontmatter, so it loads when a matching file is in play rather than waiting for someone to go looking for it. Another agent is one symlink away, though its frontmatter key differs — `paths:` for Claude, `globs:` for Cursor, `applyTo:` for Copilot.

[`.agents/`](.agents/) is the source of truth for everything this repo authors for its own agents: [`.agents/skills/`](.agents/skills/) holds the contributor skills, and `.agents/rules` points at `dev/guidelines/`. `.claude/` and `.codex/` are adapters — they hold nothing but relative symlinks into `.agents/`, so any agent that looks in its own conventional directory finds the same skills and rules, with no second copy of any of them and no adapter owning the originals.

[`skills/`](skills/) at the root is deliberately outside that scheme. It is the product: the skills the plugin ships, which `plugin.json` exposes and which `eval.yaml` reads directly. No agent working *on* this repo needs to invoke them — doing so loads the installed plugin, not your edit — so nothing routes to them. That leaves five links, and `scripts/check-symlinks.py` is what keeps them true.

| Rule | What it constrains |
| ---- | ------------------ |
| [rule-equals-test.md](dev/guidelines/rule-equals-test.md) | A new skill rule ships with its grader and eval in the same change; when the two disagree, decide which side moves |
| [graders.md](dev/guidelines/graders.md) | Parse the answer, never substring-match it; verify both directions |
| [minimum-change.md](dev/guidelines/minimum-change.md) | The smallest artifact that closes the gap, and what to delete |
| [skill-authoring.md](dev/guidelines/skill-authoring.md) | Description, body, examples, and how to verify an edit |
| [skill-registration.md](dev/guidelines/skill-registration.md) | The five surfaces a new skill has to appear in, and which of them go stale when behavior changes |
| [versioning.md](dev/guidelines/versioning.md) | The five files a version bump touches |

Each rule's `paths:` frontmatter is the authority on when
it loads; this table deliberately does not restate it.

The rules are triggers, not the reference — they state the constraint and link back into `dev/`. Before changing a skill, a grader, or an eval, read the `dev/` page the matching rule names. The architectural intent is usually the answer.

## Using the Skills From This Repo

Editing a skill here and then invoking it does not test
your edit. Three ways to exercise a skill load three
different copies:

| How | Loads | What it tests |
| --- | ----- | ------------- |
| Invoking `infrahub-*` in a session | the installed plugin under `~/.claude/plugins/cache/` | the published skill, not your edit |
| `skillgrade` | the working tree, copied into a `/tmp` sandbox | the prose, with triggering bypassed |
| Reading `skills/<name>/SKILL.md` and following it | the working tree | the prose, by hand |

Check how far apart the first two are:

```bash
uv run invoke freshness
```

To dogfood an edit through the real trigger path,
install this checkout as the plugin
(`/plugin install /path/to/infrahub-skills`, Option 3 in
[dev/guides/getting-started.md](dev/guides/getting-started.md))
and reinstall after each change — it is a copy, not a
live mount.

Note what none of the three covers: **triggering**. The
eval prompts tell the model `Read the skill at ...`, so
they exercise a skill's rules but never its
`description`, which is the field that decides whether
the skill fires at all.

## Quick Reference

### Skills

| Skill | Directory | Description |
| ------- | ----------- | ------------- |
| `infrahub-managing-schemas` | `skills/infrahub-managing-schemas/` | Schema nodes, generics, attributes, relationships (create, modify, debug) |
| `infrahub-managing-objects` | `skills/infrahub-managing-objects/` | YAML data files for infrastructure objects (create, modify, debug) |
| `infrahub-managing-checks` | `skills/infrahub-managing-checks/` | Python validation checks for proposed changes (create, modify, debug) |
| `infrahub-managing-generators` | `skills/infrahub-managing-generators/` | Design-driven automation (create, modify, debug) |
| `infrahub-managing-transforms` | `skills/infrahub-managing-transforms/` | Data transforms, Python/Jinja2 (create, modify, debug) |
| `infrahub-managing-menus` | `skills/infrahub-managing-menus/` | Custom navigation menus (create, modify, debug) |
| `infrahub-analyzing-data` | `skills/infrahub-analyzing-data/` | Live data analysis via MCP server |
| `infrahub-auditing-repo` | `skills/infrahub-auditing-repo/` | Audit repository against best practices (incl. YAGNI / cost-to-fix rules) |
| `infrahub-reporting-issues` | `skills/infrahub-reporting-issues/` | Route and prepare bug/feature reports for any opsmill/infrahub-* repo |
| `infrahub-reporting-skill-gaps` | `skills/infrahub-reporting-skill-gaps/` | Turn friction with an Infrahub skill into a bug or feature issue, filed via `infrahub-reporting-issues` |
| `infrahub-collecting-diagnostics` | `skills/infrahub-collecting-diagnostics/` | Collect a redacted local diagnostic bundle via the infrahub-collect tool (logs, config, version, state) for OpsMill expert hand-off |
| `infrahub-analyzing-diagnostics` | `skills/infrahub-analyzing-diagnostics/` | Analyze a collected diagnostic bundle: triage tracebacks/failures, correlate into incidents, match against existing GitHub issues |
| `infrahub-importing-data` | `skills/infrahub-importing-data/` | Convert CSV/TSV inputs into Infrahub object YAML and load onto a fresh branch |
| `infrahub-teaching-concepts` | `skills/infrahub-teaching-concepts/` | Tutor for Infrahub concepts: probes the learner, teaches through their own repo/instance, verified hands-on exercises, tracked progress |
| `infrahub-converting-netbox-device-types` | `skills/infrahub-converting-netbox-device-types/` | Convert NetBox device-type definitions into Infrahub object templates via a bundled, mapping-profile-driven Python converter |
| `infrahub-planning-upgrades` | `skills/infrahub-planning-upgrades/` | Plan a version-by-version upgrade path, checking each release's breaking changes against the repo and instance (read-only) |

### Rule = Test (Required)

A new rule under `skills/<skill>/rules/` ships with its
eval coverage in the same change: the rule linked from
`SKILL.md`, a check function in `graders/<skill>/lib.py`,
an `eval.yaml` task, a task grader run against four
fixtures, contradicted claims swept, and
`evaluations/*.json` regenerated.

Two of those steps carry a carve-out, for a verified rule
no prompt can make a current model break: the `eval.yaml`
task, **and the task grader script that would have no task
behind it**. Dropping only the first leaves a dead
`check_<task>.py`, which is the defect #147 was opened on.
It is a measured exception, not a judgement call, and
[rule-equals-test.md](dev/guidelines/rule-equals-test.md)
§ "When no task can score the rule" sets the bar.

The seven steps and what each one guards against live in
[dev/guidelines/rule-equals-test.md](dev/guidelines/rule-equals-test.md),
which loads automatically when you touch a rule, a
grader, or `eval.yaml`. Full walkthrough in
[dev/guides/adding-a-rule.md](dev/guides/adding-a-rule.md).

A rule without a grader is a rule that can rot silently
— the next refactor of the skill's prose loses the
constraint with no failing test to flag it. A grader
that cannot fail is worse: it reports the rule as
covered forever.

A grader that contradicts its rule is the third case.
The check is what scores, so it wins by default and the
rule rots unnoticed. Which side moves is a decision to
take when you add either one.

### Changelog

The changelog is assembled by [towncrier](https://towncrier.readthedocs.io/) from news fragments in
`changelog/`, so every change carries its own entry instead of everyone editing `CHANGELOG.md`.
Skill and tooling work goes under `housekeeping`. Add a fragment in the same PR as the change:

- `uv run towncrier create -c "Added the thing" 42.added.md` — one fragment per change, named
  `<issue>.<type>.md`. Without an issue or PR number, use a descriptive slug prefixed with `+`,
  e.g. `+netbox-device-types.added.md`.
- Types: `security`, `removed`, `deprecated`, `added`, `changed`, `fixed`, `housekeeping`.
- `uv run towncrier build --draft --version X.Y.Z` — preview the rendered changelog.
- Label a PR `ci/skip-changelog` when it genuinely needs no entry (dependency bumps, typo fixes).
  CI fails a PR that adds neither a fragment nor that label.

Do not run `towncrier build` or bump versions by hand. Merging to `main` does not prepare a
release: dispatch the **Auto bump version** workflow from Actions with `main` selected, which
opens a `chore(release): vX.Y.Z` pull request carrying the bump and the assembled changelog; the
`smoke` eval suite runs on it as the release gate, and merging it tags and publishes the
release with that changelog as the body. The version is always passed explicitly because it lives
in `plugin.json`, not in an importable package towncrier could read.

This accumulates the raw entries per PR; the curated `docs/docs/release-notes/release-X_Y_Z.mdx`
page stays a separate, hand-written narrative for each release.

Evals are tiered by cost and none of them run per PR: dispatch `skill-evals.yml` manually with
`preset: smoke` when a change needs it, `smoke` runs as a blocking check on the release PR, and the
full `regression` suite runs weekly against `main`.

### Versioning

All skills share a unified version, spread across five
files. The list, which script covers which, and what
`release.yml` does and does not validate are in
[dev/guidelines/versioning.md](dev/guidelines/versioning.md).

Each release also gets a curated notes page — see
[dev/guidelines/skill-registration.md](dev/guidelines/skill-registration.md)
for where it goes and what shifts when it lands.
