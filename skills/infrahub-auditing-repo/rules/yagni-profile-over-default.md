---
title: yagni-profile-over-default
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, profile, defaults
---

# Rule: yagni-profile-over-default

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — a cheaper built-in already covers this

## What It Checks

A Profile (`generate_profile: true` on a node, plus a Profile
instance in `objects/`) that carries a **single, fixed value set
that never varies per object**. If every object assigned the
Profile would get the exact same value, and there is no second
Profile offering a different value for the same attribute, the
Profile is doing the job of an attribute `default_value` — at the
cost of an extra node kind, a relationship, and priority
resolution.

## Why it matters

`default_value` on the attribute gives the same constant to every
object for free, in the schema, visible at the point of
definition. A Profile that only ever holds one value adds moving
parts (a Profile instance to create, assign, and keep in
existence) with no benefit: nothing varies, nothing needs central
re-tuning across competing value sets.

Reserve Profiles for values that genuinely vary across objects or
that operators re-tune centrally. One constant value is a
`default_value`.

## Checks

1. A node has `generate_profile: true` and exactly one Profile
   instance exists for it in `objects/`.
2. That Profile sets a value for an attribute that is otherwise
   identical to what a plain `default_value` would produce — no
   other Profile instance offers a competing value for the same
   attribute.
3. No object assigned the Profile depends on it being swapped for
   a different Profile later (no evidence of per-object or
   per-fleet variation in the data).

## What NOT to flag

- Nodes with **two or more** Profiles offering different values
  for the same attribute (real central tuning).
- Profiles whose values operators are expected to change over
  time across a fleet (the "edit one place" benefit is real).
- `default_value` already in use — nothing to migrate.

## Common Issues

- A single `ProfileDcimDevice` instance pinning `timezone: UTC`
  for every device that uses it, with no second profile and no
  per-device override anywhere in the data. Replace the Profile
  with `default_value: "UTC"` on the `timezone` attribute and drop
  the Profile instance and its assignment relationship.
- A "defaults" Profile created early in a project's life that was
  never joined by a second variant — the fixed value should have
  been a schema default from the start.

## Finding shape

Emit one finding per over-modeled Profile:
`{ "rule": "yagni-profile-over-default", "severity": "MEDIUM", "ladder_step": 2, "file": "<schema or profile file>", "line": "<n>" }`
