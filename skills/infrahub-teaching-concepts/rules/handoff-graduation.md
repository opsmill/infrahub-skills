---
title: End With a Graduation Pointer
impact: MEDIUM
description: >-
  Every concept closes by naming the sibling skill that does the real
  work, or the next concept on the map when the concept has no
  graduation skill.
tags: handoff, graduation, sibling-skills
---

# End With a Graduation Pointer

Impact: MEDIUM

Every concept closes by naming the sibling skill that does this work on
real projects.

## Why it matters

The tutor deliberately refuses to do the work. The learner still needs
the work done eventually; the pointer turns "lesson over" into "here is
the tool now that you understand it".

## The rule

The lesson's final lines name the matching sibling skill: schema lessons
point to infrahub-managing-schemas, objects to infrahub-managing-objects,
GraphQL to infrahub-analyzing-data, checks to infrahub-managing-checks,
transforms to infrahub-managing-transforms, generators to
infrahub-managing-generators, menus to infrahub-managing-menus. The
concept map carries the mapping. A concept whose map row has no
graduation skill (foundations, branches, repo-integration,
proposed-changes) closes by pointing to the next concept on the map
instead.

## Correct

    Next step when you are ready: the infrahub-managing-checks skill
    builds real checks for your repository.

## Incorrect

A lesson that ends at the Check section with no pointer, or one that
invokes the sibling skill instead of naming it.
