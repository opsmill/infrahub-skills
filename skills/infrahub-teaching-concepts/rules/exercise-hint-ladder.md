---
title: Hint Before Solution
impact: HIGH
description: >-
  Escalate a stuck learner through a conceptual hint, then a concrete
  pointer, then the reference solution, never handing over the answer
  on the first failed attempt.
tags: exercise, hint-ladder, pedagogy, scaffolding
---

# Hint Before Solution

Impact: HIGH

A stuck learner gets a conceptual hint, then a pointer, then the
solution. Never wrong-to-answer in one step.

## Why it matters

The moment of being stuck is where the learning happens. Handing over
the answer on the first failure converts an exercise into an example.
Withholding it forever converts a lesson into a hazing.

## The rule

On the first failed attempt, give a conceptual hint (which idea to
reconsider), with no code block longer than two lines. On the second,
give a concrete pointer (which file, field, or line). On the third
failure, or when the learner asks to see it, share the reference
solution with a walkthrough. After a solution reveal, the concept's
progress status stays `introduced`; it resurfaces in a later session.

Write each rung to `.infrahub-learning/hints/<concept>.md` under its
`## Hint N` heading before you give it. The ladder is what makes the
next rung the right one, and a session that resumes tomorrow has no
other record of which rungs the learner already climbed. Headings and
order are in `../references/lesson-protocol.md`.

## Correct

First reply to "I'm stuck": "Look at the `kind` you picked for that
attribute on `CampusSwitch`. Which choice fits a value that's set once
and never changes after that?", with the same text appended to
`hints/schema.md` under `## Hint 1`.

## Incorrect

First reply to "I'm stuck" that pastes the full solution YAML, or a
`hints/schema.md` whose first entry is `## Hint 3`.
