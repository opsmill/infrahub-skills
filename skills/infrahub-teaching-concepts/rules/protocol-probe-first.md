---
title: Probe Before Teaching
impact: CRITICAL
description: >-
  Open every concept with 2-3 questions before explaining anything, so
  the lesson anchors to what the learner already knows instead of
  guessing from job title or prior concepts.
tags: protocol, probe, pedagogy, lesson-shape
---

# Probe Before Teaching

Impact: CRITICAL

Open every concept with 2-3 questions; never assume what the learner knows.

## Why it matters

An explanation pitched at the wrong level wastes the lesson. Two questions
cost thirty seconds and tell you whether to anchor to git, NetBox, or
nothing. Inferring knowledge from job titles or earlier concepts reads as
confident and is usually wrong.

## The rule

The `## Probe` section comes first in every lesson and holds 2 or 3
questions, each on its own line ending with `?`. The first session also
asks one background question (prior tools, git familiarity) so
explanations can anchor to something known. Ask, wait, then explain. Do
not fold the explanation into the probe.

## Correct

    ## Probe
    1. Have you worked with NetBox or another source of truth before?
    2. What do you think happens when two people edit the same object?

## Incorrect

    ## Explain
    Since you are a network engineer you already know data models, so...

The lesson explains before asking anything, and guesses the background.
