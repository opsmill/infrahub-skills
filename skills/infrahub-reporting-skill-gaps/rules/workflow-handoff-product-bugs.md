---
title: Product-bug handoff
impact: HIGH
tags: workflow, handoff, routing, product-bug
---

## Product-bug handoff

Impact: HIGH

Product defects are never filed against
`opsmill/infrahub-skills`. Hand off to
[infrahub-reporting-issues](../../infrahub-reporting-issues/SKILL.md)
instead.

### Why it matters

An Infrahub server bug filed in the skills repo sits
unread until someone re-routes it by hand, exactly
the delay the user was trying to avoid by asking for
help in the first place. The skills repo has no power
to fix a product defect; only `opsmill/infrahub` (or
the relevant `opsmill/infrahub-*` product repo) does.

### What to do

1. Do not draft a `skill-friction` issue body first and
   then re-route it. `infrahub-reporting-issues` uses a
   different template and different redaction
   requirements; drafting against the wrong template and
   converting it afterward risks carrying over content
   that does not belong in the new one.
2. Invoke `infrahub-reporting-issues` with the problem
   description, in the terms that skill expects: what
   was attempted, what Infrahub returned, and the exact
   request that failed.
3. Append a note to the notes file
   (`~/.infrahub-skills/improving/notes.jsonl`, see
   [reference.md](../reference.md)) recording the
   hand-off with `status: handed-off`, so a future
   session recognizes this signature was already routed
   and does not re-triage it from scratch.

### Incorrect

```text
Drafting the skill-friction issue now:

[skill-bug] infrahub-managing-schemas: schema load 500s

... (full draft body written) ...

Actually, this looks like a server bug rather than a
skill issue. Let me change the title and repo before
showing it to you.
```

Building the wrong draft first and patching it into
shape wastes the redaction and template work twice, and
risks leftover skill-repo framing surviving into the
product-repo issue.

### Correct

```text
The skill's guidance was followed exactly as written and
Infrahub returned an unexpected 500 on a well-formed
request, so that's a product defect, not a skill gap.
Handing off to infrahub-reporting-issues to draft this
against the correct repo instead of opsmill/infrahub-skills.
Recorded the hand-off in notes.jsonl (status: handed-off).
```

Reference: [reference.md](../reference.md) for the notes
file schema; [workflow-triage-classification.md](workflow-triage-classification.md)
for the classification this hand-off follows from.
