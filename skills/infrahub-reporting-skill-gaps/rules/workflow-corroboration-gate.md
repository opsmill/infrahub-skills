---
title: Corroboration gate
impact: HIGH
tags: workflow, corroboration, gate
---

## Corroboration gate

Impact: HIGH

Do not draft an issue from a single session; require the same problem in two or more sessions, or an explicit statement from the user that it has happened before.

### Why it matters

A model can have a bad session for reasons that have nothing to do with the skill: a stale local checkout, a one-off misreading of the prompt, a genuinely ambiguous user request. Filing on one sample turns the maintainers' tracker into a log of transient failures. Each false report costs a maintainer more time to triage and close than the friction cost the user in the first place.

### What counts as corroboration

Corroboration is met by either:

- The same friction signature appearing in two or more sessions. Check the current conversation first, then check the notes file for a prior `observed` entry with a matching `skill` and `signature` (see [reference.md](../reference.md) for the schema). Re-read that entry's `transcript_path` rather than trusting the signature string alone.
- An explicit statement from the user that the problem has happened before, even without a second transcript.

A single confusing exchange, however severe, does not meet either bar on its own.

When corroboration is not met, do not draft an issue. Append one `observed` line to `~/.infrahub-skills/reporting-skill-gaps/notes.jsonl` and tell the user plainly that the observation was recorded and nothing was filed. This is not a failure state; it is the common case on first sighting.

This gate is also why step 8 matters. Once the workflow reaches a final status, filed, skipped, or deferred, write it back to the same notes file. A signature already resolved that way should not be re-raised as new the next time it is seen; the next session should find the prior decision instead of re-litigating it.

### Incorrect

```text
The schema skill got the relationship cardinality wrong once in this
session. I'll draft a GitHub issue now.

bug: infrahub-managing-schemas: relationship cardinality...

## Proposed rule change
...
```

### Correct

```text
This is the first time I've seen this friction, and one session isn't
enough to tell a pattern from a one-off. I've recorded it in
notes.jsonl (status: observed) so a future session can catch a repeat.
Nothing was filed.
```

Reference: [reference.md](../reference.md) for the notes file schema and field definitions.
