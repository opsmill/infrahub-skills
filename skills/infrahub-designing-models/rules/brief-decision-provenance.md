---
title: brief-decision-provenance
impact: HIGH
tags: brief, decisions, provenance, recommendations
---

# Rule: brief-decision-provenance

## The rule

Every decision in the brief is a row in `## Decision
log`, tagged with where it came from:

- `stated`: the user said it, unprompted or by choosing
  a non-recommended option or free text.
- `recommended`: you recommended it and the user
  accepted. The `Basis` column keeps the reason it was
  recommended.
- `open`: not decided. It also appears in Open items.

No other tags. A recommendation the user has not
accepted is `open`, not `recommended`.

## Why it matters

Whoever reviews the brief needs to know which parts of
the model the user thought through and which they
accepted from you. An accepted recommendation with a
weak basis is the first thing to check when the model
turns out wrong. Written as plain facts, the two look
the same, and the review checks neither.

## How to apply

- Log a decision when the user answers, with the
  question number in mind.
- Copy the basis from the question block that carried
  the recommendation.
- Format:
  [../references/brief-format.md](../references/brief-format.md).

## Correct

```markdown
| # | Decision | Tag | Basis |
| --- | --- | --- | --- |
| 1 | Console ports are identified by server and port number | stated | |
| 4 | Console servers and PDUs share a generic | recommended | Both have numbered ports and a management address (medium) |
```

## Incorrect

The accepted recommendation is logged as the user's own
decision, and the reason for it is lost.

```markdown
| # | Decision | Tag | Basis |
| --- | --- | --- | --- |
| 1 | Console ports are identified by server and port number | stated | |
| 4 | Console servers and PDUs share a generic | stated | |
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| `recommended` with an empty Basis | The reason to re-check it is gone |
| Tags like `agreed` or `decided` | Hide whether the user or you made the call |
| A proposed default tagged `recommended` | The user never accepted it |
