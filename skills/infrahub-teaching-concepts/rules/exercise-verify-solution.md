---
title: Verify the Exercise Before Presenting It
impact: HIGH
description: >-
  Write and verify the full reference solution to
  `solutions/<concept>.md` before showing any exercise, with real
  command evidence in `## Verification`, not a vacuous assurance.
tags: exercise, verification, solution, evidence
---

# Verify the Exercise Before Presenting It

Impact: HIGH

Build the reference solution first, prove it works, keep it hidden.

## Why it matters

Generated exercises can be unsolvable: a relationship the schema cannot
express, a query against a field that does not exist. A learner who fails
an impossible exercise learns the wrong lesson. Solving it yourself first
is the only reliable check.

## The rule

Before showing any exercise, write the full reference solution to
`.infrahub-learning/solutions/<concept>.md` with two sections:
`## Solution` (the artifact, in a code block) and `## Verification` (the
command you ran and what it reported). Verify with the method matching
the artifact type in `references/exercise-verification.md`. If the
current environment cannot verify the exercise, reshape it into one it
can verify. Never show the solution file unless the hint ladder ends.

## Correct

    ## Solution
    ```yaml
    relationships:
      - name: rack
        peer: CampusRack
        cardinality: one
    ```

    ## Verification
    Ran `infrahubctl schema check schemas/campus.yml`: loads cleanly,
    the relationship resolves.

For a conceptual exercise there is no artifact to run anything against,
so the cited docs page is the evidence: record the
`https://docs.infrahub.app/...` URL the answer derives from.

## Incorrect

Presenting an exercise with no solution file, or a solution file whose
Verification section is empty or says "should work".
