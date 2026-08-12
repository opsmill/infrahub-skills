---
title: Triage classification (level 1)
impact: HIGH
tags: workflow, triage, classification, routing
---

## Triage classification (level 1)

Impact: HIGH

Classify every piece of friction as exactly one of
three outcomes before writing any issue text: skill
defect, product defect, or neither.

### Why it matters

Drafting first and classifying later produces a draft
that gets thrown away, or worse, filed against the
wrong repo. Triage decides which repo the report goes
to, and whether it should be written at all. Getting
this step wrong either buries a real product bug in a
docs-only tracker, or asks skill maintainers to fix
something they have no power to fix.

### The three outcomes

| Classification | Meaning | Next step |
| --------------- | ------- | --------- |
| Skill defect | The guidance was missing, wrong, or unclear, and better guidance would have prevented the friction | Continue to level 2 (bug vs. feature vs. docs gap) |
| Product defect | The guidance was correct and Infrahub did the wrong thing | Hand off, see [workflow-handoff-product-bugs.md](workflow-handoff-product-bugs.md) |
| Neither | Transient, environmental, or user-specific | Record and stop |

### The discriminating question

**Would a rule change have prevented this?**

If the model followed the skill correctly and still
got a wrong result from Infrahub, no rule change
helps: that is a product defect. If the model
followed the skill correctly and the *user's*
environment or request was the actual cause (a stale
checkout, a typo, a one-off ambiguous ask), no rule
change helps either: that is neither. Only when
better wording, an added example, or a missing rule
would plausibly have changed the outcome is it a
skill defect.

Answer the question before picking the label. A label
picked first and rationalized afterward is a guess,
not a triage.

### Incorrect

```text
Four round trips, that's clearly bad. I'll classify this
as a skill defect and start drafting the issue.
```

This picks a label from how the session felt, not
from whether a rule change would have changed the
outcome. It never asks what actually caused the
friction.

### Correct

```text
The skill's rule on this topic is correct and complete;
I followed it exactly as written. Infrahub itself
returned a 500 error on a well-formed mutation that
matches the rule's example verbatim. A rule change
would not have prevented this: classification is
product defect. Handing off to infrahub-reporting-issues
rather than drafting a skill-friction issue.
```

Reference: [reference.md](../reference.md) for evidence
sources; [workflow-bug-vs-feature.md](workflow-bug-vs-feature.md)
for what happens next when the classification is skill
defect.
