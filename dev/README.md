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
- **guidelines/** — prescriptive standards per tool or
  technology.
- **specs/** — designs for changes, kept after the work
  lands as a record of intent.
- **commands/** — project-specific AI command
  definitions.

## Rules

Path-scoped rules live in [`../.agents/rules/`](../.agents/rules/)
and load automatically when a matching file is in play.
They are short triggers that point back into `dev/`;
the depth stays here.

| Rule | Fires on |
| ---- | -------- |
| `rule-equals-test.md` | `skills/*/rules/`, `graders/`, `eval.yaml` |
| `graders.md` | `graders/` |
| `skill-authoring.md` | `skills/**/*.md` |
| `skill-registration.md` | `SKILL.md`, `docs/`, `README.md` |
| `versioning.md` | version files |

Adding a rule file here is not the same as adding a
*skill* rule under `skills/<skill>/rules/` — the latter
ships with grader and eval coverage
(see [`guides/adding-a-rule.md`](guides/adding-a-rule.md)).
