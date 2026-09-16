---
paths:
  - "skills/**"
  - "graders/**"
  - "eval.yaml"
  - ".claude/skills/**"
---

# Minimum Change

Every rule carries a grader, an eval task, four fixtures, and a regression cost for the life of the repository. That cost is why the smallest artifact that closes the gap is the right one, and why this rule outranks the urge to write a new file.

## The ladder

Stop at the first rung that holds. Record the rung in the handoff file.

1. **Does this guidance need to exist at all?** A rule for a mistake no agent has actually
   made is speculative. Skip it, say so in one line. Every rule carries a grader, an eval
   task, four fixtures, and a regression cost for the life of the repository.
2. **Does the repo already say it?** An existing rule, an `examples.md` pattern, a
   `reference.md` row, a `dev/guidelines/` rule, or `infrahub-common/`. Link or tighten
   what is there. Restating a constraint in a second place is the most common slop here,
   and `skill-authoring.md` § "One fact, one home" already names it.
3. **Does an existing rule cover it in one added sentence?** Edit that rule. Do not create
   a sibling file that splits one concern across two.
4. **Is it Infrahub's job rather than the skill's?** If the product already rejects it
   (schema validator, `infrahubctl schema check`, a uniqueness constraint, an API error),
   point the agent at the error. Guidance that restates a validator rots when the validator
   changes.
5. **Can an existing grader check assert it?** Reuse the function in
   `graders/<skill>/lib.py` and add its name to an existing task's `CHECKS` list. A new
   check function is warranted only when no existing one parses the right artifact.
6. **Can it ride an existing eval task?** Add the assertion to a task whose prompt already
   produces the scenario. A new task costs trials times model runs on every regression
   sweep, forever.
7. **Can it be one line in `SKILL.md`?** One line, at the workflow step that needs it.
8. **Only then:** the minimum new artifact. One rule file, one check function, one task.
   Not a set.

## A new skill sits above all of these

A new skill costs five registration surfaces, a docs page, a manifest entry, and a version
bump, none of which CI checks. A rule inside an existing skill is the default answer.
Propose a new skill only when the domain has no home, and name the surfaces in the same
breath.

## Fixing a bug is subject to the same ladder

The common bloat on the fix side is adding a new rule where the existing rule needed one
sentence, or adding a second grader check where the existing one was simply written to
match text instead of parse structure. Fix what is wrong. Do not park a new artifact next
to it.

## Every rung has a delete counterpart

If the change makes an older rule, example, or eval task wrong, remove it in the same PR.
`harvesting-skill-review`'s "Refine, don't accrete" names the same discipline for
review-sourced rules, and the skill-change pipeline enforces it at the sweep step of
`implementing-skill-changes`.
