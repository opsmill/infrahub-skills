---
name: infrahub-reporting-skill-gaps
description: >-
  Turns friction from an Infrahub skill session into a reviewed GitHub issue against opsmill/infrahub-skills.
  Infrahub skills fail quietly: a missing or unclear rule does not crash, it produces extra round trips and
  repeated user nudges. This skill gathers evidence of that friction, checks it is corroborated, works out
  whether the skill or the underlying product is at fault, and drafts a proposed rule change. It stops at a
  user review gate and never submits without explicit approval.
  TRIGGER when: accepting a friction offer, the user says "report skill friction", asks why an Infrahub skill
  kept failing or needed so many retries, or wants a gap in an Infrahub skill's guidance reported.
  DO NOT TRIGGER when: reporting a bug in Infrahub itself or any other opsmill/infrahub-* product (use
  infrahub-reporting-issues instead), or for ordinary Infrahub work where nothing went wrong.
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - WebFetch
metadata:
  version: 1.2.8
  author: OpsMill
---

# Infrahub Skill Improver

## Overview

Infrahub skills fail quietly. A missing rule does not
crash; it produces eleven round trips and four user
nudges before the model finds the right answer on its
own. This skill works out which rule was missing,
wrong, or unclear, and drafts an improvement as a
GitHub issue against `opsmill/infrahub-skills`. It
does **not** auto-submit: it prepares a complete
draft and stops at the user's review gate. Submission
only happens after the user explicitly approves the
title and body.

## When to Use

Trigger this skill when the user says things like:

- "That took way too many tries, can you report the
  friction?"
- "Report skill friction."
- "Why did the schema skill keep getting this wrong?"
- "This skill's guidance is missing something, can we
  fix it?"

Do not trigger for a bug in Infrahub, the SDK, or any
other `opsmill/infrahub-*` product; that belongs to
[infrahub-reporting-issues](../infrahub-reporting-issues/SKILL.md).
Do not trigger for ordinary Infrahub work that
completed without friction.

## Workflow

Follow these steps in order. Stop at every gate step;
never proceed past one without explicit
confirmation.

### 1. Gather evidence

Start with the current conversation. Only look at a
past session's transcript when the user points at one.
Read [reference.md](reference.md) for how transcript
discovery works and where the notes file lives.

### 2. Check corroboration

A single confusing exchange is not evidence of a rule
gap. Require two sessions hitting the same friction, or
an explicit user confirmation that this is a recurring
problem. Otherwise append an `observed` note to the
notes file and stop; do not draft an issue yet. See
[rules/workflow-corroboration-gate.md](rules/workflow-corroboration-gate.md).

### 3. Triage: level 1, routing

Decide whether the friction is a skill defect, a
product defect, or neither. Only skill defects continue
to level 2 and drafting. See
[rules/workflow-triage-classification.md](rules/workflow-triage-classification.md).

### 3b. Triage: level 2, bug or feature

For a skill defect, decide whether it is a bug (a rule
or reference covers the topic and the model still got
it wrong) or a feature (no rule or reference covers the
topic). This decides the title prefix used in step 7.
See
[rules/workflow-bug-vs-feature.md](rules/workflow-bug-vs-feature.md).

### 4. Hand off if product

If triage points at the underlying product rather than
the skill's guidance, stop here and hand off to
[infrahub-reporting-issues](../infrahub-reporting-issues/SKILL.md)
instead of drafting a skill-friction issue. See
[rules/workflow-handoff-product-bugs.md](rules/workflow-handoff-product-bugs.md).

### 5. Locate the artifact

Find the specific rule file, or lack of one, that
should have prevented the friction. Run
`ls skills/<skill>/rules/` and grep for the topic. A
draft that cannot name the implicated file, or the gap
in coverage, is not ready. See
[rules/evidence-cite-the-artifact.md](rules/evidence-cite-the-artifact.md).

### 6. Search duplicates

Before drafting, check whether this friction is already
tracked:

```bash
gh search issues --repo opsmill/infrahub-skills --state all "<keywords>"
```

See [rules/workflow-duplicate-search.md](rules/workflow-duplicate-search.md)
for keyword selection and what to do on a match.

### 7. Draft

Fill [templates/skill-friction.md](templates/skill-friction.md).
Redact anything that identifies the user's
infrastructure or organization per
[rules/evidence-no-customer-data.md](rules/evidence-no-customer-data.md).
This is security-critical and applies before the
draft is ever shown.

### 8. Review gate

Show the user the full title and body exactly as they
would be submitted. Get explicit approval before doing
anything else. See
[rules/workflow-consent-gate.md](rules/workflow-consent-gate.md).

### 9. Record the outcome

Append the final status (filed, skipped, deferred) to
the notes file described in [reference.md](reference.md)
so a future session can find this decision instead of
re-litigating it.

## Rule Categories

| Prefix | Category | Description |
| --------- | -------- | ----------- |
| `workflow-` | Workflow | Ordering and gating: corroboration, triage, handoff, duplicate search, consent. Skipping one produces noise in the maintainers' tracker |
| `evidence-` | Evidence | What may and may not appear in a filed issue. Security-critical: issue bodies are public and cannot be retracted |

See [rules/_sections.md](rules/_sections.md) for the
index.

## Supporting References

- [reference.md](reference.md): evidence source
  priority, transcript discovery, and the notes file
  schema. **Read this in step 1.**
- [templates/skill-friction.md](templates/skill-friction.md):
  the draft template filled in step 7.
- [rules/evidence-no-customer-data.md](rules/evidence-no-customer-data.md):
  what to redact before showing a draft. Security-critical;
  read this before every draft.
- **[../infrahub-common/rules/workflow-information-priority.md](../infrahub-common/rules/workflow-information-priority.md)**
  -- Skill content first; how to consult `docs.infrahub.app`
  on a genuine gap

## Anti-patterns

- **Filing without a proposed rule change.** A friction
  report that does not name a file to create or edit,
  and what it should say, is not actionable. The
  maintainers should not have to reverse-engineer the
  fix from a symptom description.
- **Filing when the implicated skill is unknown.** If
  step 5 cannot name a skill and a rule file (or the
  absence of one), the report is not ready to draft.
- **Drafting off a single session.** The corroboration
  gate in step 2 is not optional. One confusing exchange
  is noise; a pattern is signal.
- **Pasting raw error text without redaction.** Error
  messages carry file paths, hostnames, and node kinds
  that identify a customer's infrastructure. Paraphrase,
  don't paste.
- **Submitting without showing the body.** The review
  gate in step 8 is not optional. A surprise GitHub
  issue on a public repo is hard to unwind.
