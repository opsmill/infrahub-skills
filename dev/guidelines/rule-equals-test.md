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

## When no task can score the rule

Rarely, step 4 cannot be met: the rule is correct and
verified, and no prompt makes a current model break it.
That is not licence to skip coverage. Establish it, and
say so where the next reader will look.

The bar is a measurement, not an opinion. Show the
scenarios tried, the trial scores, and the mechanism that
makes the task unbuildable rather than merely
un-hardened. "The model got it right" is the weakest
form; the useful form names why forcing the precondition
for the bug also supplies its answer.

When that bar is met:

- Ship the rule. Prose that prevents a verified bug is
  worth more than the coverage it is missing.
- Ship no task grader script. One with no task behind it
  is worse than nothing: it reads as coverage and runs
  never. That specific defect is what #147 was opened on.
- Record it here and in the pull request, not only in a
  docstring. A carve-out that lives in a grader comment
  is invisible to the next person writing a rule.
- Keep the check functions and their fixtures if they are
  sound. They pin a contract, and they are what a future
  task would wire, but be explicit that they guard the
  checks and not the prose.

Taken once, for
`skills/infrahub-managing-generators/rules/python-delete-ordering.md`
(#147). Four scenarios, around twenty trials.

The bug needs the relationship hydrated on the node being
saved. That precondition is itself the cue: once the peers
are in hand, detaching them before deleting reads as the
obvious order, and the model writes it unprompted. The
last scenario is the one that settles it, because it
reaches hydration for free through an `Attribute`-kind
relationship rather than through any call the model has to
make, and still scored 1.0 with the skill unread.

An earlier version of this entry claimed the mechanism was
`.add()` on the manager forcing hydration. That was wrong,
and it was caught in review rather than by this bar, which
is worth recording: the first three scenarios all happened
to reach hydration through `.add()`, so the sample looked
like the cause. Name the mechanism from what the scenarios
share, not from what the ones you happened to write share.

## When the grader and the rule disagree, decide which side moves

A check that encodes a stricter contract than the rule
it tests does not read as a conflict. It reads as a
passing suite, because the fixtures were written from
the check. At eval time the grader is what scores, so
the rule is the side that rots.

Four shipped in one skill, each rejecting something the
rule itself sanctioned: its canonical example, its
opt-in default, its documented carve-out, its own
non-compliant example.

Before adding a check, write out the answer the rule's
example shows, plus the answer its carve-outs allow, and
run the check on both. When they disagree, decide which
side moves and move it. Usually it is the check.

**Never let an assertion pin a defect in place.** An
invalid flag taught in eight places was also asserted by
a grader in three tasks, so a *correct* answer scored
below the CI gate. Whoever fixes the defect sees CI go
red and reverts. If a check asserts something you have
not run, it is a ratchet, not a test.

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

The rule's `impact:` frontmatter is the one that counts,
and it is also part of the grader's contract. A rule
whose prose said MEDIUM while its `impact:` said LOW
scored every answer that trusted the prose at 0.75.
Keep the level out of the prose entirely rather than
stating it twice.
