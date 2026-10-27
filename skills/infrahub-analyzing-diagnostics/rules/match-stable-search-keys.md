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

Then search — the default `gh search issues`
behavior covers open and closed issues, and a closed
match tells the user which version has the fix. Do
not pass `--state`: it only accepts `open` or
`closed`, so any value narrows the search to half
the answer (and `--state all` is rejected outright):

```bash
gh search issues --repo opsmill/infrahub "SchemaNotFoundError proposed change"
```

Run a second pass with synonyms if the first returns
nothing. If `gh` is unavailable, read the issue from
its URL with `WebFetch`, or hand the user the search
URL (`https://github.com/opsmill/infrahub/issues?q=...`).

Present the top 3-5 matches with title, state, and
URL, and say clearly when nothing matched. That
output carries no fix version — see
[reference.md](../reference.md) for the follow-up call
that finds one, and what to report when the issue
names none.

### Compliant

```text
Root error: SchemaNotFoundError ("Unable to find the
schema 'CoreProposedChange' in the registry for
branch 'atl-fix-vlans-0f3aa9c2'")

gh search issues --repo opsmill/infrahub "SchemaNotFoundError CoreProposedChange"
```

Branch name stripped; exception class and the schema
kind (stable across users) kept; no `--state` flag,
so closed-and-fixed matches surface too.

### Non-compliant

```text
gh search issues --repo opsmill/infrahub --state open "Unable to find the schema 'CoreProposedChange' in the registry for branch 'atl-fix-vlans-0f3aa9c2'"
```

The branch name is unique to this deployment — the
query can only match issues this same user already
filed. And `--state open` hides closed issues, so a
closed-and-fixed match — the best possible outcome —
would be invisible.

### Common mistakes

- Quoting the entire error message verbatim,
  volatile tokens included.
- Passing a `--state` flag at all (see above — the
  default already searches both states).
- Treating a closed match as "already fixed, upgrade"
  without opening the issue for the version the fix
  shipped in.
- Building keys from a cascade error (`Connection
  refused`) instead of the root — generic symptoms
  match hundreds of unrelated issues.
- Declaring "no known issue" after one query;
  re-query with synonyms before concluding.

Reference: [opsmill/infrahub issues](https://github.com/opsmill/infrahub/issues)
