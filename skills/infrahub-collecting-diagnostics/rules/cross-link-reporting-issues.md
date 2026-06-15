---
title: Cross-link to infrahub-reporting-issues at hand-off
impact: MEDIUM
tags: cross-link, reporting-issues, hand-off
---

## Cross-link to infrahub-reporting-issues at hand-off

Impact: MEDIUM

At the end of the workflow (step 9, hand-off), if the
user also wants to file a public GitHub issue, point
them to `infrahub-reporting-issues`. This skill never
files issues itself.

### Why it matters

`infrahub-reporting-issues` already owns the logic
for picking the right `opsmill/infrahub-*`
sub-repository, building a sanitized issue body
(versions + OS only), and running `gh issue create`.
Duplicating any of that here means two skills drift
out of sync as the upstream repo layout or
sanitization policy changes. The diagnostic bundle
is for the expert hand-off; the GitHub issue is for
the public conversation. They are different
artifacts with different audiences and different
sensitivity bars.

### What to do

At step 9 (hand-off), after the bundle is finalized,
ask the user whether they also want to file a public
issue.
If yes, hand off to `infrahub-reporting-issues` by
name. Keep the local bundle either way — it stays
the artifact the user gives to OpsMill support
out-of-band.

Do not run `gh issue create`, do not detect which
`opsmill/infrahub-*` sub-repo applies, and do not
re-sanitize bundle content for issue posting. Those
are `infrahub-reporting-issues`'s contract.

### Compliant

```text
> Bundle ready at infrahub-diagnostics-20260530-120000/.
> Hand it to OpsMill support via Discord, Slack,
> or email — it's already redacted.
>
> If you'd like to also file a public issue, use
> `infrahub-reporting-issues` next — it'll keep
> the issue body sanitized (versions + OS only).
> Keep the full bundle for the expert hand-off.
```

### Non-compliant

```text
> Bundle ready. Filing a GitHub issue now.
[skill runs `gh issue create --repo opsmill/infrahub ...`]
```

Or:

```text
> Bundle ready. Detected this is a Python SDK bug,
> so I'll target opsmill/infrahub-sdk-python.
[skill duplicates infrahub-reporting-issues' routing logic]
```

### Common mistakes

- Pasting the full diagnostic bundle into the
  GitHub issue body. The public issue gets
  versions + OS only; the bundle is private.
- Auto-routing the issue to a sub-repo from this
  skill. The routing rules live in
  `infrahub-reporting-issues` and must not be
  duplicated.
- Treating the cross-link as required. The user
  may simply hand the bundle off without filing
  any public issue at all — that is a valid
  terminal state for this workflow.

Reference: [skills/infrahub-reporting-issues](../../infrahub-reporting-issues/SKILL.md)
