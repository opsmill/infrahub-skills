---
title: yagni-generator-that-should-be-template
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, generator, object-template
---

# Rule: yagni-generator-that-should-be-template

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — a cheaper declarative layer already exists

## What It Checks

A Generator whose `generate()` only stamps out a **fixed,
near-identical structure** — the same set of child components
with constant values — and performs **no computation**: no
branching on input data, no arithmetic, no lookups, no derived
naming. When the "design" is a constant shape, an Object
Template (`generate_template: true` + clone) is the cheaper
layer.

## Why it matters

Generators are Python that runs in the pipeline: they need a
`generator_definition`, a GraphQL query, a `CoreArtifactTarget`
group, and Python maintenance. An Object Template is
declarative — enable the flag, build one curated instance,
clone it. When the generator adds nothing a template couldn't
(no computed values, no conditional structure), it is imperative
scaffolding around a job the schema does for free.

The signal is *no computation*: if you can point at the fixed
list of children and constant attributes the generator writes,
and none of it depends on the input, it is a template.

## What NOT to flag

- Generators that **compute** structure — counts derived from
  input, conditional children, names built from data, resource
  allocation. That is exactly what generators are for.
- Generators that fan out across **many parents with varying
  shape**. Templates clone one fixed shape.
- One-off **bootstrap/seed** scripts under `bootstrap/`,
  `seed/`, or `demo/` — carve-out, same as
  yagni-generator-hardcoding-data.

## Finding shape

`{ "rule": "yagni-generator-that-should-be-template", "severity": "MEDIUM", "ladder_step": 2, "file": "generators/<file>.py", "line": "<n>" }`
