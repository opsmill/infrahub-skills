---
title: Instance Writes Are Opt-In and Branch-Scoped
impact: CRITICAL
description: >-
  Reading the learner's instance is free; writing to it needs explicit
  consent, a `learning-*` branch, and a cleanup step, and it is never
  merged into the default branch.
tags: safety, branch, consent, cleanup
---

# Instance Writes Are Opt-In and Branch-Scoped

Impact: CRITICAL

The learner's instance may be production. Reading is free; writing needs
consent, a learning-* branch, and cleanup.

## Why it matters

A tutorial that mutates a production source of truth is worse than no
tutorial. Infrahub's own branching model is the safety mechanism, and
using it teaches the concept it protects.

## The rule

Three tiers, in order of preference:

1. Read-only instance access (queries, schema reads, diffs) needs no
   consent and is the default way to illustrate concepts with real data.
2. Authoring exercises happen in local files, validated offline.
3. A lesson whose subject is branches or proposed changes may write to
   the instance only after asking the learner an explicit question and
   getting a yes. All writes target a branch named `learning-<topic>`.
   The exercise ends with a cleanup step that deletes the branch. The
   branch is never merged, and nothing ever writes to the default branch.

Diagnostic or connection snippets never print credentials, not even
through a variable default like `${TOKEN:-}`.

## Correct

    This exercise writes to your instance. Shall we create a scratch
    branch for it?

    1. `infrahubctl branch create learning-pc-demo`
    2. `infrahubctl object load data.yml --branch learning-pc-demo`
    3. Clean up: `infrahubctl branch delete learning-pc-demo`

## Incorrect

    infrahubctl object load data.yml

No consent question, no branch flag: this writes to the default branch.
