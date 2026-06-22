---
title: Batch Every Ambiguity Into One Up-Front Interview
impact: CRITICAL
description: >-
  Collect every decision the skill cannot make on its own — unmapped
  dropdown cells, denormalization splits, filename overrides, branch
  name, lineage opt-in — into one multi-choice round before any file is
  written. No streaming questions during emission.
tags: workflow, interview, ambiguity, batched-questions
---

## Batch Every Ambiguity Into One Up-Front Interview

Impact: CRITICAL

Collect every decision the skill cannot make on its
own — unmapped dropdown cells, denormalization
splits, target file naming, branch name, lineage
opt-in — into a single multi-choice round before
any file is written. No streaming questions during
emission.

### Why it matters

Streaming questions during emission scatter
decisions across the run. The user can't see the
complete plan before files exist, can't review the
mapping as a whole, and any abort mid-emission
leaves a half-written directory. Batched questions
give the user one review surface.

The interview is also the only legitimate place to
skip an unmapped column — see
[workflow-fail-closed-on-unmapped-columns.md](./workflow-fail-closed-on-unmapped-columns.md).
Anything not explicitly skipped here is a hard
failure.

### What goes in the interview

| Decision | When it surfaces |
| -------- | ---------------- |
| Unmapped dropdown cell values | A cell matched neither a `name` nor a `label` in the schema's choices list |
| Denormalization split | Repeated parent columns suggest either inline component children or split-and-numbered kinds — both are valid; the user picks |
| Range collapse confirmation | A contiguous interface-shaped sequence is detected but at least one row breaks the pattern (e.g., one interface has a different role) |
| Lineage opt-in | "Stamp every value with `source: <tag>`? Yes/No, plus which Account or Repository name to use" |
| Branch name override | Default is `csv-import-YYYYMMDD-HHMM`; user can override |
| Target filename overrides | Default is `NN_<kind-plural>.yml`; user can override per file |

A template form is at the bottom of
[../reference.md](../reference.md).

### How to format the questions

- One question per ambiguity, numbered.
- Multi-choice answers where possible — a, b, c, …
  with one labeled "you tell me" or "skip."
- Each question carries enough context to answer
  without re-reading the CSV: name the column,
  name the schema attribute, name the kinds
  involved.
- No "follow-up" questions in the same round —
  surface every decision once and assume the user
  will re-run the skill if they want to revise.

### Common mistakes

- **Asking the user mid-emission what to do about
  a row that matches a previous decision.** Apply
  the previous decision; don't re-ask.
- **One question at a time over multiple
  messages.** The user can't see the full set of
  decisions and may answer inconsistently.
- **Skipping the interview because "the heuristics
  seem clear."** They aren't — the user's domain
  knowledge always matters for the split-vs-inline
  call and the lineage opt-in.

### Lock the answers before emission

After the user answers, echo back the complete
plan: each target file, each column binding, the
branch name, the lineage setting. The user gets
one chance to revise. Only then does any file get
written.

### Rationalizations — and why they don't hold

| Rationalization | Reality |
| --------------- | ------- |
| "The heuristics are clear enough to skip the interview." | The split-vs-inline and lineage calls depend on the user's domain knowledge; no heuristic can decide them. |
| "I'll ask as questions come up." | Streaming questions scatter decisions, give the user no single review surface, and break the deterministic re-run. |
| "There's only one ambiguity — I'll just ask it inline." | One question still belongs in the batched round so the locked plan is complete before any file is written. |

### Red flags — stop and batch the questions

- About to write a file before the user has confirmed the plan.
- About to send the user a second question in a separate message.
- About to resolve an ambiguity by guessing rather than asking.

Any of these means: stop, collect every open decision, and ask them in one round.

Reference: [Infrahub Docs](https://docs.infrahub.app)
