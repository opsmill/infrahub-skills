---
title: Review before sharing — masking covers key names only
impact: CRITICAL
tags: review, redaction, secrets, user-gate
---

## Review before sharing — masking covers key names only

Impact: CRITICAL

`infrahub-collect` masks values under well-known key
names (`password`/`secret`/`token`/`key` →
`********`). It does not scrub log lines, query
text, or secrets stored under any other key name.
Always walk the user through a review before the
bundle leaves their machine.

### Why it matters

Automatic masking catches the *shape* it was built
for — a config key literally named `password` or
`token`. It cannot catch a secret embedded mid-line
in a log message, a customer hostname, an internal
IP, or a credential stored under an unexpected key
name like `db_creds` or `webhook`. Treating the
tool's masking as complete would ship a bundle the
user never actually reviewed.

### What to do

After `infrahub-collect create` finishes, tell the
user plainly what is and isn't masked, then have
them scan the two highest-risk directories before
sharing:

- `bundle/logs/` — log content and query text is
  not masked; scan for secrets, internal hostnames,
  and customer-identifying data.
- `bundle/server/` — config/env output; scan for
  secrets under non-standard key names that the
  key-name masking wouldn't catch.

Get explicit confirmation from the user that the
bundle is OK to share before handing it off. Don't
skip this because the automatic masking "looked
clean."

### Compliant

```text
> Bundle created at infrahub_bundles/2026-07-16/.
> Heads up: infrahub-collect only masks values under
> keys named password/secret/token/key — it doesn't
> scrub log lines, query text, or secrets under other
> key names.
>
> Please skim bundle/logs/ and bundle/server/ for
> anything sensitive (hostnames, IPs, customer data,
> credentials under other key names) before sharing.
> Let me know when you're good to send it.
```

### Non-compliant

```text
> Bundle created and masked. Sending it to support now.
[bundle handed off without any user review]
```

### Common mistakes

- Trusting the automatic key-name masking as a
  complete redaction pass — it is not.
- Skipping the review because the bundle "looks
  fine" on a quick glance from the assistant itself,
  instead of asking the user to confirm.
- Reviewing only `bundle/server/` and skipping
  `bundle/logs/`, where unmasked query text and log
  lines are most likely to carry sensitive data.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/guides/collect-troubleshooting-bundle)
