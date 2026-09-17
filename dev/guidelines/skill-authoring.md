---
paths:
  - "skills/**/*.md"
  - "contributor-skills/**/*.md"
  - ".claude/skills/**/*.md"
---

# Skill Authoring

Full reference: `dev/knowledges/skill-writing-guide.md`
Adding a whole skill: `dev/guides/adding-a-skill.md`

## Audience

Skills explain **what** to do and the consumer-facing
**why**. No SDK source paths, no implementation tours,
no speculative edge cases the reader can fix on their
own side.

## Description field

The `description` in SKILL.md frontmatter decides
whether the skill activates at all. Include the primary
action plus specific trigger contexts, mention synonyms
users might say, and use TRIGGER / DO NOT TRIGGER to
disambiguate against neighbouring skills. Lean slightly
pushy — agents under-trigger skills.

State triggers, never a workflow summary. A description
that narrates the steps gives the agent a shortcut: it
follows the summary instead of reading the body. The
summary is also lossy in the worst direction, because
what it drops is whatever did not fit. One skill's
description omitted the step its own body flags as "the
one most easily skipped", and the section carrying its
top-priority rule, so that rule never fired at all. Name
the action and the triggers; put the ordered steps in
the body.

## Body

Structure: Overview (what and when) → Workflow
(numbered steps) → Rule Categories (links) → Supporting
References (when to read each). Keep SKILL.md under 500
lines; past that, move detail into supporting files and
leave SKILL.md as the navigator.

Explain the why, not just the what — models generalize
from reasoning better than from imperatives. Use
imperative form ("Check the namespace", not "You should
check the namespace"). Avoid piling on MUST / NEVER /
ALWAYS; too many rigid constraints make a skill brittle.

## Rules

One rule, one concern. Every rule file answers: what is
the rule, why does it matter, how to apply it, examples,
common mistakes.

Compliant and non-compliant examples go in **two
separate fenced blocks**. One fence holding both reads
as a single artifact, so the WRONG half gets copied
along with the RIGHT half.

## One fact, one home

State a list, a claim, or a command in exactly one file
and point at it from everywhere else. The failure is not
the duplication, it is the drift: a command allowlist
written into four files ends up with three different
memberships and nobody can tell which is current.

## Say only what you verified

Write the claim you tested, at the strength you tested
it. "Verified against Infrahub 1.11.0" means the check
ran on 1.11.0. An unverified provenance claim is worse
than no claim, because the next author trusts it instead
of re-checking. Before encoding a customer or PoC lesson
as a rule, verify it against current stable Infrahub —
a lesson that upstream already fixed rots the skill.

## Release-gate a command you teach

A command is only teachable once it is released. Name
the minimum version and give an observable fallback, so
a reader on an older install has somewhere to go:

```markdown
Requires infrahub-sdk >= <min version>. On
`No such command`, upgrade, or <what to do instead>.
```

Without it the reader hits `No such command` on the
documented happy path, and `infrahub-common`'s
information-priority rule tells agents this plugin
outranks the docs, so they trust the broken instruction.
One skill made an unreleased command step 6 of 7.

One home per pin, as above:
`skills/infrahub-common/marketplace-reference.md` owns
the `infrahubctl marketplace` floor, so a second skill
needing it links there rather than restating the number.

## Know what the CLI gate covers

`scripts/check-cli-invocations.py` validates the
`infrahubctl` invocations printed under `skills/`,
`graders/`, `tests/`, `eval.yaml`,
`contributor-skills/` and
most of `dev/`, against the tree pinned in
`graders/common/cli_tree.py`. Its `SCAN_TARGETS` is the
authority; `docs/`, `README.md` and `dev/specs/` are
outside it. It judges nothing else either, so a `gh`
flag, a `curl`, or a REST path is only as good as the
author who ran it. Run it, and say which version you ran
it on.

## Verifying an edit

Invoking the skill in this repository runs the installed
plugin, not the file you just changed. Check the gap with
`uv run invoke freshness`, and verify an edit through
`skillgrade` or by reading the working-tree `SKILL.md`.
See AGENTS.md § "Using the Skills From This Repo".

## Examples must stand on their own

An example is copied, not read. Each names only kinds,
attributes, fields, and packages that exist in what it
shows. Load or execute a snippet against the artifact it
sits next to before shipping it.

After editing either half, read the lead sentence and
the example together and check the example would fail
for the reason the lead gives. The commonest defect in a
corrected rule is an example demonstrating the inverse
of the sentence introducing it, because the lead was
rewritten and the example was not.

## Linting

CI lints Markdown with `rumdl` (config under
`[tool.rumdl]` in `pyproject.toml`) and YAML with
`yamllint`. Run them before pushing:

```bash
uv run rumdl check .
uv run yamllint -c .yamllint.yml .
```

A Vale prose style sits in `.vale/styles/Infrahub/`
(plain wording, Oxford commas, sentence-case headings,
`e.g.`/`i.e.` forms) but no workflow runs it today —
treat it as guidance, not a gate.

Mermaid label line breaks use a quoted label with a
literal newline, never `<br>`.
