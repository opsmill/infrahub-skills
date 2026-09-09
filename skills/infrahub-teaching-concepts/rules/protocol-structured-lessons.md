# Structured Lessons

Every lesson artifact uses the fixed section order: Probe, Explain,
Exercise, Check.

## Why it matters

The fixed shape keeps lessons consistent between sessions, makes
`.infrahub-learning/lessons/` a readable record the learner can revisit,
and gives the eval graders a deterministic surface. A lesson that skips a
section usually skipped the pedagogy behind it too.

## The rule

Write each lesson to `.infrahub-learning/lessons/<concept>.md` with
exactly these `##` headings in this order: `Probe`, `Explain`, `Exercise`,
`Check`. Concept slugs and the full workspace layout live in
`references/lesson-protocol.md`. Chat delivery mirrors the file; the file
is the record.

## Correct

    ## Probe
    ...
    ## Explain
    ...
    ## Exercise
    ...
    ## Check
    ...

## Incorrect

A lesson delivered only in chat, or a file with ad-hoc headings like
`## Theory` and `## Quiz`.
