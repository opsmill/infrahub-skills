---
title: User-gates in the diagnostic workflow
impact: CRITICAL
tags: workflow, user-gate, review
---

## User-gates in the diagnostic workflow

Impact: CRITICAL

The skill stops at four user-gates. Skipping any
gate produces an unsafe or wrong bundle.

### Why it matters

- Step 2 (connection info) — the URL and API token
  come from the user, and the token-privacy
  reassurance must be offered before any probing.
  The user may decline the token; the skill then
  records `infrahubctl_state: false` rather than
  silently assuming anonymous access.
- Step 4 (category classify) — a wrong category
  collects depth data for the wrong subsystem.
  Letting the user correct or pick "everything"
  mode prevents this.
- Step 7 (redaction review) — auto-redaction
  catches known secret shapes only. The user
  knows which IPs/hostnames/customer strings are
  sensitive to them; only they can decide.
- Step 9 (hand-off) — the user controls where the
  bundle goes (Discord, Slack, an issue). Auto-
  uploading anywhere is not allowed.

### What to do

At each gate, present a clear summary and a small
set of choices. Wait for the user's explicit
response. Do not proceed on silence or ambiguity.

### Compliant

```text
> Step 4 — I classified this as `git-sync`
> because the error mentions `CommitNotFoundError`
> and your `.infrahub.yml` registers two repos.
> Confirm, override with another category, or
> switch to "everything" mode?
```

### Non-compliant

```text
> Detected git-sync. Running collection now...
[commands fire without user confirmation]
```

### Common mistakes

- Treating step 4 as advisory ("I'll classify but
  collect everything anyway") — defeats the
  purpose of asking.
- Auto-applying redaction choices to all groups
  because "they all look like the same kind of
  data" — they may not be.
