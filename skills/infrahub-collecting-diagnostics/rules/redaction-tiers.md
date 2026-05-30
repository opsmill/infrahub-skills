---
title: Two-tier redaction — automatic plus user-review gate
impact: CRITICAL
tags: redaction, secrets, pii, user-gate
---

## Two-tier redaction — automatic plus user-review gate

Impact: CRITICAL

Bundles must be safe to share by default. The skill
applies Tier 1 (automatic secret masking) first, then
stops at Tier 2 (user-review gate) before finalizing.
Both tiers are required; skipping either produces an
unsafe bundle.

### Why it matters

Tier 1 catches the *shape* of known secrets — env
keys named `PASSWORD`, JWT-shaped tokens, AWS keys,
private-key blocks. It does not catch *meaning*: a
public IP address, a customer hostname, or a webhook
URL is structurally benign but may be confidential
to the user. Only the user knows. Skipping Tier 2
because Tier 1 "looked clean" ships a bundle the
user never consented to share.

### What to do

**Tier 1 (automatic).** Apply to every text, YAML,
and JSON file in the bundle. Log every replacement
with file + line in `redaction-report.txt`.

| Pattern | Replacement |
|---|---|
| Env keys matching `(PASSWORD\|SECRET\|TOKEN\|CLIENT_SECRET\|API_KEY\|AWS_SECRET_ACCESS_KEY\|DSN\|AUTH)`, case-insensitive | `***REDACTED:env-key***` |
| URL credentials `https?://user:pass@` | `https://***REDACTED***@` |
| JWT shapes (three base64 segments dot-joined) | `***REDACTED:jwt***` |
| AWS access keys `AKIA[0-9A-Z]{16}` + 40-char Base64 secret | `***REDACTED:aws***` |
| Private-key blocks (`-----BEGIN ... PRIVATE KEY-----`) | Stripped entirely |
| UUIDs adjacent to `INFRAHUB_INITIAL_ADMIN_TOKEN` / `INFRAHUB_INITIAL_AGENT_TOKEN` | `***REDACTED:init-token***` |

**Tier 2 (user-review gate).** After Tier 1 runs,
print a one-screen summary: N files touched, M
replacements by category, plus distinct samples
the user must classify. Sample groups:

- Top 10 RFC1918 IPs + top 10 public IPs found in
  logs or config.
- Distinct hostnames present in logs and GraphQL
  responses.
- Distinct customer-/device-looking strings from
  `CoreAccount` and schema-export top values.
- All webhook URLs (Slack, Discord, PagerDuty,
  custom).

For each group ask `keep` / `redact-all` /
`case-by-case`. Record the user's choice in
`manifest.yml` under `redaction.user_choices` and
re-run masking accordingly. Set
`redaction.user_review_completed: true` only after
the user has answered every group.

**Diagnostic-signal flags (not values).**
`INFRAHUB_SECURITY_SECRET_KEY` and
`INFRAHUB_INITIAL_ADMIN_TOKEN` are diagnostically
meaningful — multi-pod JWT bugs (e.g.
[#8925](https://github.com/opsmill/infrahub/issues/8925))
hinge on whether the defaults are still in use. The
value itself is always redacted, but the manifest
records `using_default_security_key: true|false`
and `using_default_init_token: true|false` by hash
comparison against the upstream docker-compose
defaults.

### Compliant

```yaml
# bundle/baseline/config/compose-resolved.yml
environment:
  INFRAHUB_DB_PASSWORD: ***REDACTED:env-key***
  INFRAHUB_SECURITY_SECRET_KEY: ***REDACTED:env-key***
```

```yaml
# bundle/manifest.yml (excerpt)
infrahub:
  using_default_security_key: true
  using_default_init_token: false
redaction:
  user_review_completed: true
```

### Non-compliant

```yaml
# bundle/baseline/config/compose-resolved.yml
environment:
  INFRAHUB_DB_PASSWORD: hunter2          # raw value shipped
  INFRAHUB_SECURITY_SECRET_KEY: 327f...  # raw value shipped
```

### Common mistakes

- Skipping Tier 2 because Tier 1 "looked clean".
  Tier 1 cannot judge what is sensitive to *this*
  user; only Tier 2 can.
- Over-redacting OAuth2 provider names (`github`,
  `okta`) because they appear next to a secret.
  The provider name is diagnostic; only the secret
  value is sensitive.
- Recording the raw `INFRAHUB_SECURITY_SECRET_KEY`
  instead of the `using_default_*` boolean. The
  default-vs-custom signal is the diagnostic; the
  value is not.

Reference: [Configuration reference](https://docs.infrahub.app/reference/configuration)
