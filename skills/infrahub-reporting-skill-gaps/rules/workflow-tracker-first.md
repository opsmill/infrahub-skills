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

An earlier version of this rule blocked on local
corroboration: two sessions on this machine, or nothing
gets drafted. That gate cannot pass. Sessions are
partitioned by working directory, and a skill's users
share none of it. Two clones, two worktrees, two
customer repos, a laptop and a devbox, or two engineers
hitting the same missing rule all read as first
sightings forever.

Worse, the gate suppresses exactly what it claims to
look for. A first sighting recorded nowhere public
means the second observer, on another machine, also
sees a first sighting and is also suppressed. The
pattern becomes undetectable by construction.

The tracker has none of these problems. It is shared,
it is global, it survives a wiped laptop, and a
maintainer reading it has the view no single session
ever has.

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
I searched opsmill/infrahub-skills and found no open issue covering
enum default values in schema attributes. This is a single observation,
so the draft says so explicitly rather than claiming a pattern.

bug: infrahub-managing-schemas: enum attribute default value syntax
  is not covered by any rule

> Confidence: unconfirmed single observation.
```

### Also correct

```text
Issue #142 already covers this friction. Rather than filing a duplicate,
I've drafted a comment adding what this session showed that the issue
does not yet record: the failure also occurs on schema load, not only
on validation.
```

Reference: [reference.md](../reference.md) for evidence
sources and friction signals.
