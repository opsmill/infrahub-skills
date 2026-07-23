---
title: Hand off at the skill boundaries
impact: MEDIUM
tags: cross-link, hand-off, reporting-issues, collecting-diagnostics
---

## Hand off at the skill boundaries

Impact: MEDIUM

This skill sits between two siblings and must hand
off at both edges: no bundle yet →
`infrahub-collecting-diagnostics`; filing or
commenting on a GitHub issue →
`infrahub-reporting-issues`. Searching issues is
this skill's job; *submitting* anything is not.

### Why it matters

`infrahub-collecting-diagnostics` owns safe
collection (the binary, the flags, the
review-before-sharing gate);
`infrahub-reporting-issues` owns repo routing, issue
sanitization (versions + OS only), and the
user-review gate before submission. Duplicating
either here means the logic drifts as those skills
evolve — and skipping their gates means unreviewed
content lands on a public tracker or a hand-rolled
log scrape replaces a proper bundle.

### What to do

- **Missing/incomplete bundle** → hand off to
  `infrahub-collecting-diagnostics`, naming the
  `create` flags the findings call for
  (`--include-queries`, `--benchmark`, ...). Never
  scrape live logs from here. Treat
  `--include-backup` as the last resort: it exists
  so an expert can reproduce the problem locally,
  and a minimal reproducible example (the specific
  schema/objects/steps from the incident) serves
  that goal with far less data exposure — recommend
  the MRE first.
- **User wants to file, or comment on a matched
  issue** → hand off to `infrahub-reporting-issues`
  with the incident summary and candidate issue
  URLs. Never run `gh issue create` (or an MCP
  submission) from this skill; `gh search issues`
  is fine.
- **Expert hand-off** → the bundle plus this report
  go to OpsMill support, behind the
  review-before-sharing gate the collecting skill
  defines. The findings report quotes log excerpts,
  so it needs the same review as the bundle itself.

### Compliant

```text
Incident 1 matches open issue opsmill/infrahub#5891.
To add your reproduction as a comment, continue with
infrahub-reporting-issues — it will keep the comment
sanitized (versions + OS only). This report + bundle
can also go to OpsMill support after you review both
for sensitive content.
```

### Non-compliant

```text
No matching issue found — filing one now:
gh issue create --repo opsmill/infrahub --title "Database OOM" --body "$(cat findings-report.md)"
```

Files without the reporting skill's review gate and
pastes an unsanitized report (log excerpts,
hostnames) into a public issue.

### Common mistakes

- Pasting findings-report excerpts (which quote
  logs) into a public issue body — the public issue
  gets versions + OS only, via
  `infrahub-reporting-issues`.
- Re-implementing repo routing here (SDK vs main
  repo, etc.) — that logic lives in
  `infrahub-reporting-issues`.
- Treating hand-off as mandatory: "no known issue,
  nothing to file, report delivered" is a valid
  terminal state.

Reference: [skills/infrahub-reporting-issues](../../infrahub-reporting-issues/SKILL.md)
