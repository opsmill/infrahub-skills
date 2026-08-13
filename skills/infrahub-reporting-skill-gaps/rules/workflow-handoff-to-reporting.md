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

`{repo, type, title, body, searched, issue?}`, where
`type` is `bug`, `feature`, or `docs gap`, and `repo`
follows the kind: `opsmill/infrahub-skills` for a bug or
a feature, `opsmill/infrahub` for a docs gap, since
Infrahub's own documentation lives there, not in the
skills repo. See
[workflow-bug-vs-feature.md](workflow-bug-vs-feature.md)
for the routing table and the settled-behavior gate a
docs gap must also pass before it is drafted at all.

`searched` names the repo this skill already searched at
step 2, so the receiver knows whether its own duplicate
search is redundant or still owed. `issue` is optional:
present, it carries the number of the issue the step-2
search matched, and `body` is a comment rather than a
new issue. One payload with an optional field, not two
shapes, so every field the receiver already handles
keeps working unchanged.

### Why it matters

`infrahub-reporting-issues` already owns the 11-repo
registry, the consent gate, submission-method choice,
comment mode, and confirmation. A second filing pipeline
built here would duplicate all of that and then drift
from it: when the repo registry changes, or the
submission method changes, only one of the two pipelines
gets updated, and the other quietly goes stale.

Duplicate search is the one exception, and it is a
narrow one. This skill has to know whether an issue
already exists *before* it drafts, because the answer
decides whether the draft is a comment or a new issue
and what confidence label it carries; see
[workflow-tracker-first.md](workflow-tracker-first.md).
The receiver searches late, just before filing. Passing
`searched` is what keeps that from becoming two searches
and two answers that can disagree in public.

### What this skill must NOT do

- Run `gh issue create` or `gh issue comment`.
- Ask the user how they want to submit.
- Claim that an issue was filed, commented on, or
  otherwise submitted.

Every one of those belongs to
`infrahub-reporting-issues`. Doing them here produces
two consent gates and a user asked the same question
twice.

`gh search issues` is **not** on that list. Step 2
requires it. Searching reads; only writing to GitHub is
reserved for the receiver.

### What this skill MUST do

Produce a complete, redacted body and title, then
invoke `infrahub-reporting-issues` with the payload and
let it drive from there: the review gate, submission
method, and confirmation are all its job now, as is any
duplicate search still owed for a repo `searched` does
not name.

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
Draft complete and redacted:

feat: infrahub-managing-checks: no guidance on sharing GraphQL fragments across check files

## Proposed rule change
Add a rule file describing how to import a fragment
defined in another check module, with a compliant
example.

Handing off to infrahub-reporting-issues with:

  repo: opsmill/infrahub-skills
  type: feature
  title: (the line above)
  body: (the full report, including the section above)

infrahub-reporting-issues will search for duplicates,
show the draft for review, and handle submission from
here.
```

A docs-gap handoff targets the other repo, and drops the
`[skill]` segment from the title since it means nothing
to `opsmill/infrahub`'s maintainers:

```text
Draft complete and redacted:

bug(docs): no documentation on multi-hop relationship
traversal in a GraphQL query

## Proposed rule change
Document cursor-based multi-hop relationship traversal
in a GraphQL query, since Infrahub supports it today and
its behavior is settled; only the documentation is
missing.

Handing off to infrahub-reporting-issues with:

  repo: opsmill/infrahub
  type: docs gap
  title: (the line above)
  body: (the full report, including the section above)

infrahub-reporting-issues will search for duplicates,
show the draft for review, and handle submission from
here.
```

Reference:
[workflow-tracker-first.md](workflow-tracker-first.md)
for the step-2 search that fills `searched` and `issue`;
[workflow-bug-vs-feature.md](workflow-bug-vs-feature.md)
for how `type` was decided.
