---
name: infrahub-teaching-concepts
description: >-
  Teaches Infrahub concepts (schema, objects, branches, proposed changes,
  checks, transforms, generators, menus) from wherever the learner is,
  using their own repo files and live instance as lesson material.
  TRIGGER when: the user wants to learn or understand an Infrahub concept,
  asks "teach me", "explain how X works in my instance", "I'm new to
  Infrahub", asks what the equivalent of a NetBox/Nautobot concept is in
  Infrahub, wants a guided tour, or wants to resume a learning session.
  DO NOT TRIGGER when: the user wants the work done for them (use the
  infrahub-managing-* skills), wants live operational answers (use
  infrahub-analyzing-data), or is debugging a failure (use
  infrahub-collecting-diagnostics).
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
argument-hint: "[concept-or-question]"
metadata:
  version: 1.2.8
  author: OpsMill
---

# Infrahub Concept Tutor

## Overview

A tutor protocol, not a textbook. It measures what the learner already
knows, explains each concept through the learner's own schema, objects,
and instance where they exist, sets a hands-on exercise the learner solves
themselves, and records progress so a later session resumes instead of
restarting. Exercises are verified solvable before they are shown.

## When to Use

- "Teach me how relationships work" or any concept question asked to learn
  rather than to delegate.
- "Why does my instance behave this way?" when the goal is understanding.
- "What's the NetBox/Nautobot equivalent of X in Infrahub?" taught as a
  translation (see `rules/grounding-competitor-mapping.md`).
- "Where were we?" to resume from `.infrahub-learning/progress.md`.

## Environment Detection

Detect once per session, in this order, and prefer the richest source:

1. Repo files in the cwd (schema YAML, object files, `.infrahub.yml`):
   teach through the learner's own artifacts.
2. A reachable Infrahub instance (MCP server or `infrahubctl`): read-only
   queries illustrate concepts with real data.
3. Neither: use the generic examples in `references/concept-map.md`.

Instance safety has three tiers; the full ladder is in
`rules/safety-instance-writes.md`. The short form: read-only by default,
author in local files, and write to the instance only after explicit
consent, only in a `learning-*` branch, never merged, always deleted.

## Workflow

1. On first contact, offer to create the learning workspace and read
   `references/lesson-protocol.md` for the exact file layout and lesson
   shape. On resume, read `.infrahub-learning/progress.md` first.
2. Pick the concept with `references/concept-map.md`: it orders concepts
   by prerequisite and carries per-concept probe questions, exercise
   specs, verification methods, and doc anchors. A topic with no row is
   taught off-map through the shared docs fallback
   (`rules/grounding-off-map-lookup.md`).
3. Run the lesson: Probe, Explain, Exercise, Check, then record progress.
   Before presenting the exercise, build and verify the reference
   solution per `references/exercise-verification.md`.
4. When the learner struggles, follow the hint ladder in
   `rules/exercise-hint-ladder.md`.
5. Close each concept by naming the sibling skill that does this work on
   real projects.

## Rule Categories

See `rules/_sections.md`. Read the rules for the lesson phase you are in;
they are short and binding.

## Supporting References

- `references/lesson-protocol.md`: the workspace contract and lesson
  shape. This file is the single home for those values.
- `references/concept-map.md`: the curriculum.
- `references/exercise-verification.md`: how to prove an exercise is
  solvable before showing it.
- `../infrahub-common/`: shared GraphQL syntax and `.infrahub.yml` format.
