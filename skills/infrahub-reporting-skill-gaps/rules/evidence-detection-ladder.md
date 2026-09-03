---
title: Detection ladder
impact: HIGH
tags: evidence, detection, verifier, coverage
---

## Detection ladder

Impact: HIGH

A friction report rests on a verdict, never on a memory of how the session
felt. There is no declared-intent artifact to diff a skill session against,
so the oracle is Infrahub's own verifiers and the skill's own ruleset. Work
the four probes below in order.

### Probe A: verifier verdict

Look for a red-to-green transition on the same target: `infrahubctl schema
load`, `infrahubctl schema validate`, `infrahubctl object load`,
`infrahubctl check run`, `infrahubctl transform run`, or a `pytest` run of a
check's or transform's tests. Something that failed and later passed is the
strongest evidence available, because no self-assessment produced it. The
failing output names the topic; the passing version names the fix.

Two conditions bound it:

- **The skill must have been loaded before the first attempt.** A failure on
  work authored without the skill says nothing about the skill's guidance.
- **Not every failure is a skill gap.** Authentication, connectivity, a
  missing container, or a product-side 500 exit to level-1 triage; see
  [workflow-triage-classification.md](workflow-triage-classification.md).

### Probe B: coverage read

Run `ls skills/<skill>/rules/` and grep the topic terms. A hit where the
output was still wrong points at a bug; no hit points at a feature or a docs
gap. This is the same read step 5 performs, run early so the citation and
the level-2 kind come out of one investigation instead of two.

Probe A without probe B is incomplete. A tells you something broke; B tells
you which file owns it.

### Probe C: correction delta

Diff the first authored version of the artifact against the version that was
finally accepted. That delta **is** the proposed rule change, stated in the
concrete terms a maintainer can apply, rather than a paraphrase of it. Read
it from the session's own edit history, or from `git diff` when the file was
committed. It is often unavailable, after a compaction for instance, and its
absence never blocks a report.

### Probe D: session-shape counters

These open an investigation. They never close one:

- Two or more error results on the same tool and the same target
- Three or more edits to one artifact inside a single task
- A user turn restating the same ask, or correcting the previous answer
- A fetch of `docs.infrahub.app`, `llms.txt`, or `schema.infrahub.app` after
  the relevant skill file was already read
- Four or more rule files read before the first edit, which points at
  discoverability rather than coverage

A draft whose only support is counters is not ready. Say which probe came up
empty and stop, rather than converting a retry count into a claim about
guidance.

### Why it matters

Round trips and nudges measure a session, not a ruleset. Both rise for
reasons that have nothing to do with the skill: an unclear request, a slow
instance, a user changing their mind. Filing on that signal alone puts
reports in the tracker that no maintainer can act on, and buries the ones
backed by a verdict.

### Incorrect

```text
The schema skill took eleven round trips and I nudged it four times before
it got there, so the relationship guidance has a gap.
```

Counters only. No verifier outcome, no named file, nothing a maintainer can
open.

### Correct

```text
`infrahubctl schema load` rejected the file twice, then passed once an
`identifier` was set on the generic side of the relationship. The skill was
loaded before the first attempt, and the failure was a validation rejection,
not a connectivity or auth error.

Grepping `skills/infrahub-managing-schemas/rules/` for the topic names
relationship-identifiers.md, which documents the bidirectional case but
never the generic-peer one. The delta between the rejected and accepted file
is that single `identifier` key, which is the proposed rule change.
```

Reference: [evidence-cite-the-artifact.md](evidence-cite-the-artifact.md)
for what counts as naming the file probe B finds;
[workflow-bug-vs-feature.md](workflow-bug-vs-feature.md) for the level-2
kind probe B feeds; [../reference.md](../reference.md) for the evidence
sources these probes read.
