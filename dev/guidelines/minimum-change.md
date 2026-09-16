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
   made is speculative. Skip it, say so in one line.
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
5. **Can it be one line in `SKILL.md`?** One line, at the workflow step that needs it.
6. **Only then:** the minimum new artifact. One rule file, one check function, one task.
   Not a set.

Every rung is an exit: answer yes and you write nothing new, or you edit something that
already exists. Two coverage questions used to sit here, asking whether an existing grader
check or an existing eval task could carry the assertion. Neither is an exit, since a
grader check with no rule attached is not a change anyone can ship, so they now live in
`test-driving-skill-changes`, asked at the point where a new check or task is about to be
written.

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
