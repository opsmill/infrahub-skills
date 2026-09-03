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

`{type, title, body, searched, issue?}`, where `type` is
`bug`, `feature`, or `docs gap`. See
[workflow-bug-vs-feature.md](workflow-bug-vs-feature.md)
for how `type` was decided and the settled-behavior gate
a docs gap must also pass before it is drafted at all.

**No `repo` field.** This skill never names a filing
destination. The receiver resolves the repo from `type`
against its own registry; see its Skill-gap intake
section. Routing is the one thing it owns outright, and a
copy of the mapping here is a copy that goes stale the
first time the destination changes.

`searched` names the repo this skill already searched at
step 2, so the receiver knows whether its own duplicate
search is redundant or still owed. That is a statement of
what was read, not a destination. `issue` is optional:
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
- Name the repo the issue will be filed against.
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

  type: feature
  title: (the line above)
  body: (the full report, including the section above)
  searched: opsmill/infrahub-skills (no match)

infrahub-reporting-issues resolves the target repo from
the type, shows the draft for review, and handles
submission from here.
```

A docs-gap handoff carries a different `type`, which is
what routes it elsewhere, and drops the `[skill]` segment
from the title since the originating skill means nothing
to the maintainers who will receive it:

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

  type: docs gap
  title: (the line above)
  body: (the full report, including the section above)
  searched: opsmill/infrahub-skills (no match)

A docs gap does not belong to the skills repo, so the
receiver's own duplicate search is still owed against
wherever it routes this. It will run that search, show
the draft for review, and handle submission from here.
```

Reference:
[workflow-tracker-first.md](workflow-tracker-first.md)
for the step-2 search that fills `searched` and `issue`;
[workflow-bug-vs-feature.md](workflow-bug-vs-feature.md)
for how `type` was decided.
