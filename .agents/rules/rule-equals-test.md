---
paths:
  - "skills/*/rules/*.md"
  - "graders/**/*.py"
  - "eval.yaml"
---

# Rule = Test

Full procedure: `dev/guides/adding-a-rule.md`

A new rule under `skills/<skill>/rules/` ships with its
eval coverage **in the same change**. A rule without a
grader rots silently: the next refactor of the skill's
prose drops the constraint with no failing test to flag
it. A grader that cannot fail is worse — it reports the
rule as covered forever.

## What a rule change must include

1. The rule file at
   `skills/<skill>/rules/<category>-<concern>.md`, using
   an existing category prefix from the skill's
   `rules/_sections.md`.
2. A link from `SKILL.md` **at the workflow step that
   needs it**, saying *when* to read it.
   `_sections.md` is a table of contents, not a load
   trigger — a rule reachable only from there gets read
   after the mistake.
3. A check function in `graders/<skill>/lib.py`,
   registered in `CHECKS`, parsing the answer rather
   than substring-matching it (see `graders.md`).
4. A task block in `eval.yaml` whose prompt naturally
   exercises the rule, verified to **fail** with the
   instruction's `Read the skill at ...` line commented
   out.
5. A task grader script at
   `graders/<skill>/check_<task>.py`, run against four
   fixtures: compliant, compliant phrased differently,
   violating, and a violating near-miss that satisfies
   the check's keyword.
6. Old claims the rule contradicts swept from `skills/`,
   `graders/`, and `eval.yaml`:

   ```bash
   grep -rn "<old claim, command, or field>" \
     skills/ graders/ eval.yaml dev/
   ```

   Skip `evaluations/` — step 7 regenerates it.
7. `python scripts/sync-evals.py`, with the regenerated
   `evaluations/*.json` committed alongside `eval.yaml`.
   CI fails when the two diverge.

## New category prefixes

A new prefix must be registered everywhere the skill
enumerates its categories, not only in `_sections.md`:

- `rules/_sections.md` — the prefix and its scope
- the `Rule Categories` table in `SKILL.md`
- any severity or ladder legend the skill keeps
  (`infrahub-auditing-repo` has one in both
  `audit-procedure.md` and `SKILL.md`)

A prefix registered in only one of those is a rule the
skill never emits, while its eval still passes.

## Severity

`yagni-*` audit rules cap at MEDIUM. HIGH and CRITICAL
are for real failures, not advisory cost-to-fix
findings. An impact or severity label changed in a rule
has to move in the skill's index too.
