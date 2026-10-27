---
title: Cite the Docs for Behavior Claims
impact: HIGH
description: >-
  Every taught claim about Infrahub behavior carries a
  `docs.infrahub.app` link in the Explain section, placed next to the
  claim it supports.
tags: grounding, docs, citations, explain
---

# Cite the Docs for Behavior Claims

Impact: HIGH

Every taught claim about how Infrahub behaves carries a
docs.infrahub.app link in the Explain section.

## Why it matters

Generated explanations can drift from current Infrahub behavior. The doc
link is the learner's escape hatch and the tutor's grounding: if no page
supports the claim, do not teach the claim.

## The rule

The `## Explain` section contains at least one working
`https://docs.infrahub.app/...` link, placed with the claim it supports.
Use the per-concept anchors in `references/concept-map.md`. Version-pin
any claim that changed between Infrahub releases.

## Correct

    Cardinality controls how many peers one object can have. See
    https://docs.infrahub.app/schema/overview for the full model.

## Incorrect

An Explain section with confident behavior claims and no link, or a link
dumped at the end without connection to any claim.
