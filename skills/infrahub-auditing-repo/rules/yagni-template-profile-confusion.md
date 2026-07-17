---
title: yagni-template-profile-confusion
impact: MEDIUM
ladder_step: 3
tags: audit, yagni, profile, object-template
---

# Rule: yagni-template-profile-confusion

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 3 — the right tool is cheaper than the workaround

## What It Checks

The two features used for each other's job:

- An **Object Template** used to push shared *values* everyone
  should have — the same constant attributes copied into every
  cloned instance, with no structural children that justify a
  template. That is a Profile's job.
- A **Profile** (or many near-duplicate Profiles) used to
  approximate cloning a *structure* — e.g. modeling child
  components as repeated Profile values. Profiles move values,
  not related objects; that is a Template's job.

## Why it matters

Templates clone once and diverge; Profiles link live. Push a
shared value through a template and every clone freezes a copy
— change the value and you must edit every instance, the exact
pain Profiles exist to remove. Conversely, straining a Profile
to recreate structure it cannot own leads to brittle, partial
models. Using the tool that matches the intent (values →
Profile, structure → Template) removes invisible complexity.

## What NOT to flag

- A node that legitimately uses **both** for their proper jobs
  (template clones structure; Profile supplies shared values).
- A template that copies attribute values **as a starting
  point users then diverge from** — that is normal template
  behavior, not value-sharing.

## Finding shape

`{ "rule": "yagni-template-profile-confusion", "severity": "MEDIUM", "ladder_step": 3, "file": "<file>", "line": "<n>" }`
