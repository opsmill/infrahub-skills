---
title: Capture Infrahub URL and API token up front, with privacy guarantee
impact: CRITICAL
tags: workflow, user-gate, privacy
---

## Capture Infrahub URL and API token up front

Impact: CRITICAL

Before any `infrahubctl` call, the skill asks the
user for the Infrahub URL and an API token, with a
specific privacy guarantee for the token. If the
user declines the token, the skill falls back
gracefully to a token-free collection path.

### Why it matters

`infrahubctl` talks to Infrahub via two environment
variables:

- `INFRAHUB_ADDRESS` — the URL or IP of the
  deployment (e.g., `http://localhost:8000`,
  `https://infrahub.example.com`). The skill cannot
  guess this for any non-local deployment.
- `INFRAHUBCTL_TOKEN` — the API token. Required for
  any deployment that has anonymous access disabled,
  which is the typical case in production.

Asking these as a user-gate matters for two reasons:

1. **The skill can't fake the URL.** Defaulting to
   `http://localhost:8000` works for a laptop demo
   and breaks on every other deployment. Asking is
   the only correct behavior.
2. **The token request is the highest-friction step
   in the entire workflow.** Customers and prospects
   are reasonably nervous about handing an AI tool a
   credential. **Without explicit consent and a
   strong reassurance, the answer is no token, and
   the bundle is partial.** The skill must present
   the reassurance verbatim and accept "no" without
   pressure.

### What to do

Ask both questions early — right after step 1
(Capture the problem), before any probing. Two
prompts:

1. "What URL or IP should `infrahubctl` use to reach
   Infrahub? (For example,
   `http://localhost:8000` or
   `https://infrahub.example.com`.)"

2. The token request, with this **verbatim** privacy
   notice:

   > Your API token is only used locally by
   > `infrahubctl` to query state on your behalf. It
   > is never written to the bundle. The skill's
   > redactor masks the token before any bundle file
   > is finalized. The token is not sent anywhere
   > outside your machine.

3. Optionally: "If you want to scope the diagnostic
   to a specific branch instead of the default, what
   branch name?"

When the user shares the values:

- Export `INFRAHUB_ADDRESS=<url>` and
  `INFRAHUBCTL_TOKEN=<token>` in the shell for the
  rest of the workflow.
- **Immediately** add the token string to the
  Tier-1 redactor mask list — before the next
  `infrahubctl` call runs. This guarantees that if
  any downstream command accidentally echoes the
  token (a debug log, an `infrahubctl --verbose`,
  etc.), the bundle redactor masks it.

When the user declines the token (a legitimate "I
don't give credentials to AI tools" — never push
back):

- Do not pressure. Acknowledge and continue.
- Run the topology / log / host / file-read
  collection. None of these need a token.
- Skip every `infrahubctl` state query (branches,
  repos, schema, tasks, telemetry).
- Record `collected.infrahubctl_state: false` in
  `manifest.yml` so the expert sees the bundle is
  partial and why.
- In `README.md`, note: "Token withheld; bundle
  contains topology + logs + file reads only.
  Instance state (branches, repos, schema, tasks,
  telemetry) is not included."

### Compliant

A skill turn that looks like this:

```text
Skill:  Before I start probing, I need two things:

        1. The URL or IP `infrahubctl` should use to reach Infrahub.
           E.g., http://localhost:8000 or https://infrahub.example.com.

        2. An API token. Your API token is only used locally by
           infrahubctl to query state on your behalf. It is never
           written to the bundle. The skill's redactor masks the
           token before any bundle file is finalized. The token is
           not sent anywhere outside your machine.

User:   URL is https://infrahub.acme.example.
        Token: ABC...XYZ

Skill:  Thanks — adding the token to the redactor mask list now,
        exporting INFRAHUB_ADDRESS and INFRAHUBCTL_TOKEN, and
        continuing with the baseline.
```

Or, with a decline:

```text
Skill:  [same prompt as above]

User:   I don't want to share a token with an AI tool.

Skill:  Understood — I'll collect topology, logs, host fingerprint,
        and file reads, and skip everything that needs infrahubctl
        against the instance. I'll record that the bundle is partial
        in manifest.yml and call it out in README.md.
```

### Non-compliant

- The skill assumes `INFRAHUB_ADDRESS=http://localhost:8000`
  and anonymous access, then `infrahubctl branch list`
  fails with `401 Unauthorized` and the bundle has
  empty state files. No prompt.
- The skill asks for the token without the privacy
  notice. The user is left to guess what happens to
  the credential.
- The user declines, and the skill keeps trying
  `infrahubctl` calls anyway (they'll fail, but the
  bundle ends up with a wall of `401` error pages
  instead of a clean "skipped" record).
- The token is received and the skill runs an
  `infrahubctl` call before adding the token to the
  redactor mask list. A verbose echo could now end up
  in a log file that the redactor doesn't catch.

### Common mistakes

- **Asking for the token without the privacy
  reassurance.** Even if the underlying behavior is
  correct, the user has no way to know it without
  the explicit statement. Most will say no.
- **Forgetting to add the token to the redactor mask
  list before any `infrahubctl` call.** The order
  matters: mask first, call second.
- **Treating "no token" as a failure rather than a
  partial-bundle path.** Token-decline is a
  supported, first-class outcome. The bundle is
  still useful to the expert — logs and topology
  alone resolve a substantial fraction of issues.
- **Defaulting silently to anonymous access when the
  user doesn't reply.** Always ask. Always wait for
  an answer.

Reference:
[docs.infrahub.app — infrahubctl auth](https://docs.infrahub.app/infrahubctl/infrahubctl).
