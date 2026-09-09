---
title: Off-Map Concepts Go Through the Shared Docs Fallback
impact: HIGH
description: >-
  A concept absent from the concept map is taught from a docs page
  found through the shared information-priority rule, never
  improvised from memory.
tags: grounding, off-map, docs-fallback, concept-map
---

# Off-Map Concepts Go Through the Shared Docs Fallback

Impact: HIGH

A concept the map does not cover is taught from a docs page found
through the shared information-priority rule, never from memory.

## Why it matters

Learners ask about webhooks, number pools, and whatever shipped last
month. Refusing to teach off-map concepts makes the tutor brittle;
improvising them from model memory is how stale or invented behavior
gets taught. The shared rule already defines the safe path to the docs,
and defining it a second time here is how the two copies drift apart.

## The rule

When the requested concept has no row in `references/concept-map.md`,
run the docs fallback exactly as
[workflow-information-priority.md](../../infrahub-common/rules/workflow-information-priority.md)
defines it; that rule owns the lookup mechanics and this rule does not
repeat them. Then teach the off-map lesson in the full four-section
shape under its own slug (not a map slug), cite the found page in
Explain, give it a progress row, and tell the learner the concept came
from the docs fallback rather than the curriculum. That statement
doubles as the signal that the concept is a candidate for the map. If
the fallback finds no page covering the topic, say so and stop; do not
teach an ungrounded lesson.

## Correct

    This one is not in my curriculum, so I looked it up in the Infrahub
    docs index. Lesson saved as lessons/webhooks.md, grounded in
    https://docs.infrahub.app/topics/webhooks.

## Incorrect

Answering a webhooks question from memory with no docs lookup, or
cramming the topic into the nearest map concept's lesson file.
