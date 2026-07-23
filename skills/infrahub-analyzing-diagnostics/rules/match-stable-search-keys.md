---
title: Search GitHub with stable traceback keys
impact: HIGH
tags: match, github, search-keys, tracebacks
---

## Search GitHub with stable traceback keys

Impact: HIGH

When matching an incident against existing GitHub
issues, build the search query from the parts of the
error that are the same for every user who hits the
bug — and strip the parts that are unique to this
deployment.

### Why it matters

An issue filed by someone else contains *their*
branch names, UUIDs, and hostnames — not this
user's. A search that includes volatile tokens
(`atl-fix-vlans-0f3aa9c2`, `10.0.4.17`, a timestamp)
returns zero results for a bug that is already filed
and already fixed, so the user files a duplicate or
waits on support for a known problem. The stable
parts — exception class, the constant fragment of
the message, the raising module — are what all
occurrences of the bug share.

### What to do

Extract from the root error (not cascade noise):

- The **exception class** (e.g.
  `SchemaNotFoundError`), unqualified — issue titles
  rarely include the full dotted path.
- The **stable message fragment** — the message with
  IDs, UUIDs, branch names, hostnames, IPs, paths,
  and timestamps removed (e.g. `Unable to find the
  schema` — not the schema of branch
  `atl-fix-vlans-0f3aa9c2`).
- Optionally the **innermost Infrahub frame**
  (module or function name) when the message alone
  is too generic.

Then search both open and closed issues — a closed
match tells the user which version has the fix:

```bash
gh search issues --repo opsmill/infrahub --state all "SchemaNotFoundError proposed change"
```

Run a second pass with synonyms if the first returns
nothing. If `gh` is unavailable, fall back to a
GitHub MCP tool if present, or give the user the
search URL
(`https://github.com/opsmill/infrahub/issues?q=...`).
Present the top 3-5 matches with title, state, and
URL, and say clearly when nothing matched.

### Compliant

```text
Root error: SchemaNotFoundError ("Unable to find the
schema 'CoreProposedChange' in the registry for
branch 'atl-fix-vlans-0f3aa9c2'")

gh search issues --repo opsmill/infrahub --state all "SchemaNotFoundError CoreProposedChange"
```

Branch name stripped; exception class and the schema
kind (stable across users) kept.

### Non-compliant

```text
gh search issues --repo opsmill/infrahub "Unable to find the schema 'CoreProposedChange' in the registry for branch 'atl-fix-vlans-0f3aa9c2'"
```

The branch name is unique to this deployment — the
query can only match issues this same user already
filed. `--state all` is also missing, so a
closed-and-fixed match would be invisible.

### Common mistakes

- Quoting the entire error message verbatim,
  volatile tokens included.
- Searching open issues only — a closed match is the
  best possible outcome (the fix exists; check the
  version it shipped in).
- Building keys from a cascade error (`Connection
  refused`) instead of the root — generic symptoms
  match hundreds of unrelated issues.
- Declaring "no known issue" after one query;
  re-query with synonyms before concluding.

Reference: [opsmill/infrahub issues](https://github.com/opsmill/infrahub/issues)
