# Developer Documentation

Internal documentation for contributors working on the
skills themselves. For user-facing docs, see
[`docs/`](../docs/) (published to Docusaurus).

## Quick Navigation

| I want to... | Go to |
| ------------ | ----- |
| Understand how the plugin is put together | [`knowledges/architecture.md`](knowledges/architecture.md) |
| Install the plugin and run the workflow | [`guides/getting-started.md`](guides/getting-started.md) |
| Create a new skill | [`guides/adding-a-skill.md`](guides/adding-a-skill.md) |
| Add or tighten a rule | [`guides/adding-a-rule.md`](guides/adding-a-rule.md) |
| Run or write evals | [`guides/running-evals.md`](guides/running-evals.md) |
| Write skill prose that works | [`knowledges/skill-writing-guide.md`](knowledges/skill-writing-guide.md) |
| Look up an Infrahub concept | [`knowledges/infrahub-concepts.md`](knowledges/infrahub-concepts.md) |
| See what a past change was designed to do | [`specs/`](specs/) |

## Directory Guide

- **guides/** — step-by-step procedures. How to do a
  specific task.
- **knowledges/** — descriptive reference. How the
  system works and why it is shaped that way.
- **guidelines/** — prescriptive rules, each scoped by a
  `paths:` glob. `.claude/rules` symlinks here, so a rule
  loads when a matching file is in play.
- **specs/** — designs for changes, kept after the work
  lands as a record of intent.
- **commands/** — project-specific AI command
  definitions.

Contributor skills live outside `dev/`, in
[`../.claude/skills/`](../.claude/skills/), because that
is where an agent discovers them:
[`harvesting-skill-review`](../.claude/skills/harvesting-skill-review/SKILL.md)
turns a PR's review threads into rules, and the
skill-change pipeline
([`analyzing-skill-bugs`](../.claude/skills/analyzing-skill-bugs/SKILL.md),
[`grilling-skill-features`](../.claude/skills/grilling-skill-features/SKILL.md),
[`test-driving-skill-changes`](../.claude/skills/test-driving-skill-changes/SKILL.md),
[`implementing-skill-changes`](../.claude/skills/implementing-skill-changes/SKILL.md))
takes a bug or an idea
through a failing test to a pull request.

Agents other than Claude Code do not look in `.claude/` or `dev/` by
default, so `.agents/` and `.codex/` each symlink `skills`, the contributor
skills, and the rules into the directory that agent expects. See
[`../AGENTS.md`](../AGENTS.md#rules) for what each link points at.

## Rules

`guidelines/` is the canonical home for path-scoped
rules. Each file declares in frontmatter the globs it
applies to, and `.claude/rules` symlinks to the
directory, so an agent loads a rule when it touches a
matching file rather than when someone remembers to go
looking. The rules are triggers; the depth stays in
`guides/` and `knowledges/`.

The rules and what each constrains are listed once, in
[`AGENTS.md` § Rules](../AGENTS.md#rules). Each rule's
`paths:` frontmatter is the authority on when it loads.
Neither place restates the globs: a second copy drifts,
which is what `guidelines/skill-authoring.md`
§ "One fact, one home" is about.

Another agent is one symlink away: point its rules
directory here too, and check its frontmatter keys — the
`paths:` Claude reads is `globs:` in Cursor and
`applyTo:` in Copilot.

Adding a file here is not the same as adding a *skill*
rule under `skills/<skill>/rules/` — the latter ships
with grader and eval coverage
(see [`guides/adding-a-rule.md`](guides/adding-a-rule.md)).
