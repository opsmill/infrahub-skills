---
title: Handoff to reporting-issues
impact: CRITICAL
tags: workflow, handoff, routing, filing
---

## Handoff to reporting-issues

Impact: CRITICAL

Never file directly. Hand the payload to
[infrahub-reporting-issues](../../infrahub-reporting-issues/SKILL.md)
and let it drive submission from there.

### The payload

`{repo, type, title, body}`, where `repo` is always
`opsmill/infrahub-skills` and `type` is `bug` or
`feature`.

### Why it matters

`infrahub-reporting-issues` already owns the 11-repo
registry, duplicate search, comment mode, the consent
gate, submission-method choice, and confirmation. A
second filing pipeline built here would duplicate all
of that and then drift from it: when the repo registry
changes, or the submission method changes, only one of
the two pipelines gets updated, and the other quietly
goes stale.

### What this skill must NOT do

- Run `gh issue create`.
- Run `gh search issues`.
- Ask the user how they want to submit.
- Claim that an issue was filed, commented on, or
  otherwise submitted.

Every one of those belongs to
`infrahub-reporting-issues`. Doing them here produces
two consent gates, two duplicate searches, and a user
asked the same question twice.

### What this skill MUST do

Produce a complete, redacted body and title, then
invoke `infrahub-reporting-issues` with the payload and
let it drive from there: duplicate search, the review
gate, submission method, and confirmation are all its
job now.

### Incorrect

```text
Drafting complete. Filing now:

$ gh issue create --repo opsmill/infrahub-skills \
    --title "feat: infrahub-managing-checks: no guidance on sharing GraphQL fragments across check files" \
    --body "..."

Issue filed: https://github.com/opsmill/infrahub-skills/issues/142
```

This skill ran `gh issue create` itself and claimed a
result. It never touched the consent gate, duplicate
search, or submission-method choice that
`infrahub-reporting-issues` provides, so nothing here
was actually reviewed or checked for duplicates.

### Correct

```text
Draft complete and redacted. Handing off to
infrahub-reporting-issues with:

  repo: opsmill/infrahub-skills
  type: feature
  title: feat: infrahub-managing-checks: no guidance on sharing GraphQL fragments across check files
  body: <full redacted report>

infrahub-reporting-issues will search for duplicates,
show the draft for review, and handle submission from
here.
```

Reference:
[reference.md](../reference.md) for the notes file
schema; [workflow-bug-vs-feature.md](workflow-bug-vs-feature.md)
for how `type` was decided.
