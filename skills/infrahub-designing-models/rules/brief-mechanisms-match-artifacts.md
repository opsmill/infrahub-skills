---
title: brief-mechanisms-match-artifacts
impact: HIGH
tags: brief, mechanisms, generator, check, transform, artifacts
---

# Rule: brief-mechanisms-match-artifacts

## The rule

`## Mechanisms` is a table, in the format in
[../references/brief-format.md](../references/brief-format.md),
and it agrees with the Features table both ways:

1. Every `generator`, `check` or `transform` a feature
   lists in `Artifacts` has at least one row with that
   mechanism for that feature.
2. Every row with one of those mechanisms belongs to a
   feature whose `Artifacts` list it.
3. `Mechanism` is one of `generator`, `check`,
   `transform`, `computed attribute`, `resource pool`,
   `schema constraint`.
4. For F1, `Driven by`, `Produces` and `Runs when` are
   answered or name an open item, and a generator is
   driven by a node kind from the sketch.

A rule the schema can enforce, such as "no two of these
share a value", is a `schema constraint`, not a `check`.
When the user asked for a check for such a rule, do not
list `check` in Artifacts: record the schema constraint,
and log the replacement as an `open` decision that names
their request, so they can still ask for the check.

## Why it matters

The skill that builds a generator, a check or a
transform needs decisions only the user can make: which
object drives it, what it produces, when it runs. Without
them, the brief hands that skill one word in the
Artifacts column and it has to guess. A check written for
a rule the schema already enforces is code to maintain
for nothing, and it runs later than the schema would.

## How to apply

- For each behavior the user describes, decide the
  mechanism with the Mechanism question in
  [../references/question-bank.md](../references/question-bank.md).
- Ask what each generator, check or transform needs from
  the rules of the skill that will build it: list
  `../../infrahub-managing-generators/rules/`,
  `../../infrahub-managing-checks/rules/` or
  `../../infrahub-managing-transforms/rules/` when the
  design includes that artifact, and read the rules that
  govern a decision in front of you. These rules change
  over time; read them, do not recall them.
- Add the artifact to the feature's `Artifacts` when you
  add the row, and the other way round.

## Correct

```markdown
| Feature | Behavior | Mechanism | Driven by | Produces | Runs when | Why |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | A new console server gets its port objects | generator | ConsoleServer | ConsolePort per port | a console server is added | creates other nodes from a design |
| F1 | No two console servers share a hostname | schema constraint | ConsoleServer | uniqueness on hostname | every change | the schema enforces it without code |
```

## Incorrect

The feature lists a generator with no row for it, and a
uniqueness rule is written as a check.

```markdown
| Feature | Behavior | Mechanism | Driven by | Produces | Runs when | Why |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | No two console servers share a hostname | check | ConsoleServer | a failed proposed change | on proposed change | catch duplicates |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Mechanisms written as prose | The building skill cannot tell what drives what |
| A generator driven by "the team" | A generator runs from a node kind, not a person |
| A check for uniqueness | The schema enforces it earlier and without code |
