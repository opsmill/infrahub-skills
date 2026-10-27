---
title: Rule Title Here
impact: MEDIUM
tags: tag1, tag2
---

## Rule Title Here

Impact: MEDIUM

One-sentence statement of the rule.

### Why it matters

Two to four sentences naming the concrete consequence
of getting this wrong across Infrahub workflows
(generators, checks, transforms, object loading) — the
validation error users see, the silent drift between
code and schema, the partial sync that looks healthy
but isn't. Pin to the actual mechanism, not generic
"best practice" framing.

### Symptoms

What the user sees when the rule is violated (error
text, UI behavior, missing data).

### Cause

The mechanism that produced the symptom — why
Infrahub, the SDK, or git is behaving that way.

### Fix

```yaml
# Corrective example
```

### Prevention

How to avoid hitting this in the first place.

Reference: [Infrahub Docs](https://docs.infrahub.app)
