---
title: Record Progress
impact: CRITICAL
description: >-
  Offer the `.infrahub-learning/` workspace on the first lesson and
  upsert `progress.md` after every concept, using the exact header and
  the three defined statuses.
tags: protocol, progress, workspace, statuses
---

# Record Progress

Impact: CRITICAL

Offer the learning workspace on the first lesson and update
`progress.md` after every concept.

## Why it matters

Learning Infrahub spans sessions. Without a progress file every session
restarts with the same probes, and "where were we?" has no answer. With
one, resuming costs one file read.

## The rule

On the first lesson, offer to create `.infrahub-learning/` (never create
it unasked). After each concept, upsert a row in
`.infrahub-learning/progress.md` using the exact table header and the
three statuses defined in `references/lesson-protocol.md`: `not-seen`,
`introduced`, `practiced`. On resume, read `progress.md` before probing.
A concept whose exercise needed the solution revealed stays `introduced`.

## Correct

| concept | status | last-seen | notes |
| --- | --- | --- | --- |
| schema | introduced | 2026-09-09 | solution revealed |

## Incorrect

Inventing statuses (`mastered`, `done`), renaming columns, or promoting a
concept to `practiced` after handing over the solution.
