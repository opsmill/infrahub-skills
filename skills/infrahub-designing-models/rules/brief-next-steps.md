---
title: brief-next-steps
impact: MEDIUM
tags: brief, next-steps, handoff, workflow
---

# Rule: brief-next-steps

## The rule

The brief ends with `## Next steps`: a numbered list,
in the format in
[../references/brief-format.md](../references/brief-format.md),
that a person can follow.

1. Open items that F1's sketch waits on come first.
2. Each feature has a step, after the steps of the
   features it depends on.
3. Each feature's step is worded for the workflow the
   repository already uses. Detect it, do not ask:
   `.specify/` means spec-kit, so the step gives the
   feature's Handoff to `/speckit.specify`; another
   specification or planning setup gets the Handoff; with
   none, the step names the skill for each artifact, in
   the order of the `Artifacts` cell.

The Handoff cells stay workflow-neutral. Only Next steps
names the reader's own workflow.

## Why it matters

The plan map shows the order and the Features table
holds the details, but neither tells a person what to do
on Monday morning. A brief read by a person, by spec-kit
and by an agent does not need three files; it needs the
tables for tools and one short list for people.

## How to apply

- Write Next steps last, from the finished Features
  table and Open items.
- Keep one step per feature; put independent features in
  any order after their dependencies.

## Correct

```markdown
## Next steps

1. Settle O1 with network operations.
2. Build F1 Console access: run the Schema Manager, then the Object Manager and the Generator Manager.
3. When F1 is loaded, build F2 Console audit with the Schema Manager and the Check Manager.
```

## Incorrect

F2 comes before the F1 it depends on, and the open item
F1 waits on is left for the end.

```markdown
## Next steps

1. Build F2 Console audit.
2. Build F1 Console access.
3. Settle O1.
```
