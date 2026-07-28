---
title: User-gates in the diagnostic workflow
impact: CRITICAL
tags: workflow, user-gate, review
---

## User-gates in the diagnostic workflow

Impact: CRITICAL

The skill stops at two user-gates. Skipping either
produces an unsafe bundle or an unwanted hand-off.

### Why it matters

- Step 5 (review before sharing) — `infrahub-collect`
  only masks values under well-known key names. The
  user knows which hostnames, IPs, or customer data
  in the bundle are sensitive to them; only they can
  approve sharing it.
- Step 6 (hand-off) — the user controls where the
  bundle goes (Discord, Slack, email, or additionally
  a public GitHub issue). Auto-sending it anywhere,
  or auto-filing an issue, is not allowed.

### What to do

At each gate, present a clear summary and wait for
the user's explicit response. Do not proceed on
silence or ambiguity.

### Compliant

```text
> Bundle created. Before I consider this done, please
> skim bundle/logs/ and bundle/server/ for anything
> sensitive — let me know when it's OK to share.
```

### Non-compliant

```text
> Bundle created. Sending it to support now.
[bundle handed off without any user confirmation]
```

### Common mistakes

- Treating the review-before-sharing gate as
  optional because the tool already applied some
  masking — the masking is key-name-only and does
  not cover log/query content.
- Assuming the user wants a GitHub issue filed
  automatically once the bundle is ready — always
  ask first, and hand off to
  `infrahub-reporting-issues` rather than filing it
  from here.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
