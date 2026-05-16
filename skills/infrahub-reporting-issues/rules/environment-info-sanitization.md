# Rule: env-info-sanitization

**Severity**: CRITICAL
**Category**: Environment info

## What It Checks

Bug reports filed against public GitHub repos must
not leak internal infrastructure details. The bug
section of an issue body is rendered publicly, indexed
by search engines, and cannot be reliably retracted
once submitted. This rule defines what is and is not
allowed to appear in the environment section of a
generated bug report.

## Why It Matters

Once an issue is filed on a public repo:

- It is indexed by GitHub search, Google, and AI
  training scrapers within hours.
- Editing or deleting the issue does not remove it
  from those caches.
- Internal hostnames, IP ranges, and container names
  reveal network topology that can be cross-referenced
  with the user's employer.
- Tokens, even partial ones, are immediately scraped
  by automated bots and used for credential stuffing.

The cost of a single leaked production hostname can
exceed the lifetime cost of every other skill in this
plugin combined. The sanitization rule is the most
load-bearing rule in this skill — get this one wrong
and the rest of the workflow is irrelevant.

## What Is Allowed

The environment section may contain **only**:

1. **Product versions** — e.g., `infrahub-sdk 1.5.2`,
   `infrahub-server 1.4.0`. Public software versions
   are not sensitive.
2. **OS + architecture** — e.g., `macOS 14 arm64`,
   `Ubuntu 22.04 x86_64`. Generic OS info is not
   sensitive.
3. **Runtime version** — e.g., `Python 3.12`,
   `Node 20`. Not sensitive.

Anything else requires explicit justification AND
explicit user opt-in.

## What Must Be Redacted

The following patterns must never appear in the
issue body. If detected, replace with the listed
placeholder.

| Pattern | Replace with |
| ------- | ------------ |
| IPv4 addresses (e.g., `10.20.30.40`) | `<internal-ip>` |
| IPv6 addresses | `<internal-ipv6>` |
| Hostnames containing internal/private TLDs (`.local`, `.internal`, `.corp`, `.lan`, or any custom org domain mentioned by the user) | `<internal-host>` |
| URLs pointing to internal services (e.g., `https://infrahub.acme.corp`) | `<internal-url>` |
| API tokens, JWTs, Bearer tokens, anything matching `gh[pousr]_[A-Za-z0-9]{36,}` or other obvious secret patterns | **abort and ask the user** |
| Filesystem paths containing usernames (e.g., `/Users/alice/...`, `/home/bob/...`) | `<path>` |
| Container names, pod names, k8s namespaces from the user's environment | `<container>` / `<namespace>` |
| Database connection strings | **abort and ask the user** |
| Email addresses (other than the user's GitHub-visible address) | `<email>` |

## Abort-and-ask cases

If the issue body would contain a token, secret, or
database connection string after sanitization
attempts, **stop**. Do not file the issue. Tell the
user what was detected, where, and ask them to
manually rewrite that section. Do not try to "fix"
secrets by partial redaction — bots will still try
the partial value.

## Examples

**Compliant environment section**:

```markdown
## Environment

- infrahub-sdk: 1.5.2
- infrahub-server: 1.4.0
- OS: macOS 14 arm64
- Python: 3.12.1
```

**Non-compliant** (leaks hostname, path, IP):

```markdown
## Environment

- infrahub-sdk: 1.5.2
- Connected to https://infrahub.acme.corp
- Config at /Users/alice/work/acme-infra/config.yml
- Server IP: 10.50.12.7
```

**After sanitization**:

```markdown
## Environment

- infrahub-sdk: 1.5.2
- Connected to <internal-url>
- Config at <path>
- Server IP: <internal-ip>
```

## Common Mistakes

- Pasting `infrahubctl --version` output verbatim
  when it includes a server URL.
- Including stack traces without scrubbing file
  paths (they typically contain `/Users/<name>/`).
- Pasting `pip list` or `pip freeze` output — far
  more than the required versions, and may reveal
  private package indexes via implicit context.
- Leaving the user's email in `git config user.email`
  output when it's an internal-domain email.
- Believing partial token redaction is safe.
  `gh${actual_letters}_xxx...` is still scraped.
- Forgetting that container names often encode
  team/project names from internal conventions.
