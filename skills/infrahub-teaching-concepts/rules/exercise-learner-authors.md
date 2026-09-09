---
title: The Learner Writes the Artifact
impact: HIGH
description: >-
  The tutor assigns and reviews the exercise but never authors the
  artifact itself, and never leaks the reference solution into the
  lesson file.
tags: exercise, authorship, pedagogy, solution-hiding
---

# The Learner Writes the Artifact

Impact: HIGH

The tutor assigns and reviews; it never authors the exercise artifact.

## Why it matters

Watching Claude write YAML teaches nothing durable. The learning happens
in the learner's own attempt and the review of it. A completed artifact
in the lesson is homework done for them.

## The rule

The `## Exercise` section assigns work with a line starting exactly
`**Your task:**`. The tutor does not write the exercise artifact, does
not include the solution in the lesson, and does not invoke the sibling
`infrahub-managing-*` skills mid-lesson (they exist to do the work, which
is the opposite of this skill's job). Review the learner's attempt
against the hidden reference solution.

## Correct

    ## Exercise
    **Your task:** Add a relationship from `CampusSwitch` to
    `CampusRack` in your schema file. Tell me when you want a review.

## Incorrect

An Exercise section that contains the finished YAML, or a lesson that
calls infrahub-managing-schemas to produce it.
