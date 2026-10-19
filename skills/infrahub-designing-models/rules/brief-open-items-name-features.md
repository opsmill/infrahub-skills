---
title: brief-open-items-name-features
impact: MEDIUM
tags: brief, open-items, features, traceability
---

# Rule: brief-open-items-name-features

## The rule

Every open item names the features its answer changes:

```markdown
- O2: Who owns cabling records? (owner: unknown, NOC or facilities; affects F1, F3)
```

1. Each item names at least one feature from the
   Features table.
2. Every feature with a cell that says `open: O<n>`, in
   the sketch or in Mechanisms, is in that item's list.

## Why it matters

Open items get answered later, often after a feature
has been specified or built. When the user comes back
with an answer, the skill has to know which features
the answer changes, and which of those are already past
`planned`. An item that says nothing about the features
it touches leaves the change to be found by reading
every table, and a feature already built gets changed
without anyone noticing it needs a migration.

## How to apply

- Write the list when you write the item, from the
  cells that refer to it and the features its question
  is about.
- When the user returns with an answer, follow SKILL.md
  "Coming back with an answer".

## Correct

```markdown
- O1: Who owns the channel plan? (owner: unknown, optical or planning team; affects F2)
```

## Incorrect

The item names no feature, so an answer later cannot
show what it changes.

```markdown
- O1: Who owns the channel plan? (owner: unknown, optical or planning team)
```
