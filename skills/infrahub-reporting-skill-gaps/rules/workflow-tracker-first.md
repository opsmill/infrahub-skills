---
title: Tracker first
impact: HIGH
tags: workflow, tracker, corroboration
---

## Tracker first

Search `opsmill/infrahub-skills` for an existing report
of the same friction before drafting anything. The
search decides the **shape** of the report, never
whether there is one.

### Why it matters

A skill's users share no repo, directory, or laptop, so
local session history cannot answer "has anyone seen
this before". Only the tracker can: it is shared, it
survives a wiped machine, and a maintainer reading it
has the view no single session ever has.

This is also why a first sighting still gets written
down. An observation recorded nowhere public is
unrecoverable, and the next person to hit it starts
from zero, which makes the pattern undetectable by
construction.

### What to do

Search first, using the friction in the user's own
terms plus the implicated skill name:

```bash
gh search issues --repo opsmill/infrahub-skills \
  --state all "<skill name> <friction in plain terms>"
```

Then take one of three paths:

| Result | Action |
| ------ | ------ |
| An issue already covers this friction | Draft a **comment** on it carrying only the new evidence from this session. Do not draft a second issue. |
| No match, and the user says it has happened before | Draft a new issue, labelled `recurring` in the body. |
| No match, and this is a first sighting | Draft a new issue, labelled `unconfirmed single observation` in the body. |

A single observation is weak evidence, not zero
evidence. Label it honestly and let the maintainer
judge. A thin issue takes seconds to close; an
observation that was never written down cannot be
recovered.

When `gh` is unavailable or unauthenticated, say so,
ask the user whether they have hit this before, and
treat the answer as `recurring` or `unconfirmed`. Do
not fall back to mining local transcripts to
manufacture a second data point.

### Incorrect

```text
The schema skill got the relationship cardinality wrong once in this
session. I'll draft a GitHub issue now.

bug: infrahub-managing-schemas: relationship cardinality...
```

Drafted blind. It may duplicate an open issue, and it
claims a confidence one session does not support.

### Also incorrect

```text
This is the first time I've seen this friction, and one session isn't
enough to tell a pattern from a one-off. Nothing was filed.
```

Suppression. The observation dies here and the next
person to hit it starts from zero.

### Correct

```text
I searched opsmill/infrahub-skills. Issue #142 already covers this
friction, so rather than filing a duplicate I've drafted a comment
adding what this session showed that the issue does not yet record:
the failure also occurs on schema load, not only on validation.
```

The no-match branch is the same search followed by a
new issue whose body carries
`**Confidence**: unconfirmed single observation`.

Reference: [reference.md](../reference.md) for evidence
sources and friction signals;
[workflow-handoff-to-reporting.md](workflow-handoff-to-reporting.md)
for the `searched` and `issue` fields this step fills in
the handoff payload.
