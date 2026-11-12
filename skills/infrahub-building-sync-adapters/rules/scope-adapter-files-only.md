---
title: Change Only the Adapter Files, and Draft Core Issues Instead
impact: HIGH
description: >-
  An adapter change touches only infrahub_sync/adapters/<name>.py plus its
  tests, example, docs, changelog fragment and spec. Never edit other
  infrahub_sync files such as rest_api_client.py, utils.py, the core models or
  the loader: write a private helper in the adapter module and draft a core
  issue. Check with git diff --stat after each commit.
tags: scope, core, infrahub-sync, git, issue
---

## Change Only the Adapter Files, and Draft Core Issues Instead

An adapter change touches only these files in the
infrahub-sync checkout:

- `infrahub_sync/adapters/<name>.py`;
- its tests and fixtures under `tests/`;
- its example under `examples/`;
- its docs page and the adapter lists under `docs/`;
- its news fragment under `changelog/`;
- its spec under `dev/specs/` (or `specs/`).

Every other file under `infrahub_sync/` stays as it is:
`rest_api_client.py`, `utils.py`, the core models, the
Infrahub adapter, the loader, the CLI. This holds even
when the cleanest fix seems to be a shared helper.

### Why it matters

A core change in an adapter pull request changes the
behavior of every adapter and every customer's sync, and
it is reviewed as part of an adapter, which is the wrong
review. On the Webex adapter, the first implementation
round changed core files (identifier checks in the
Infrahub adapter, `--continue-on-error` on `diff` in the
CLI). The user rejected the round as "really bad", and it
was reverted file by file.

### How to apply

- **Need a helper?** Write it as a private function
  (`_next_link`, `_retry_after_seconds`) inside the
  adapter module, and keep the HTTP client in that module
  too.
- **Want the shared version, or found a core bug?**
  Draft a core issue instead of a fix. Save it as a
  Markdown file at the top of the working directory (for
  example `core-issue-next-link-helper.md`), keep it out
  of the adapter commit, and give it to the user to
  file. Write:
  - the problem, with the observed behavior and how to
    reproduce it;
  - the proposed change in core;
  - the adapters that would use it;
  - the workaround in this adapter (the private helper's
    name).
- **After each commit, run the scope check.** It must
  print nothing:

```bash
git diff --stat "<base>" -- infrahub_sync ':!infrahub_sync/adapters/<name>.py'
```

`<base>` is the commit the adapter branch started from,
for example the output of
`git merge-base HEAD origin/main`. Any line in the output
is a core file to revert before going on.

### Correct

The pagination helper lives in the adapter module, and a
core issue proposes the shared version:

```python
# infrahub_sync/adapters/netinventory.py
import re

_LINK = re.compile(r"<([^>]*)>([^,<]*)")
_REL = re.compile(r'(?:^|;)\s*rel="?([^";]+)"?', re.IGNORECASE)


def _next_link(link_header: str | None) -> str | None:
    """The rel="next" URL of a Link header, selected exactly (never prev or last), whatever the parameter order."""
    for url, params in _LINK.findall(link_header or ""):
        rel = _REL.search(params)
        if rel and "next" in rel.group(1).split():
            return url
    return None
```

### Incorrect

"One small helper" added to a core module, so every
adapter's import surface changes in an adapter pull
request:

```python
# infrahub_sync/adapters/utils.py
def next_link(response):
    return response.links.get("next", {}).get("url")
```

### Common mistakes

- **Adding the helper to `utils.py` or to
  `rest_api_client.py`** "so other adapters benefit".
  Propose that in the core issue.
- **Fixing a core bug found during live validation** in
  the adapter branch, instead of drafting an issue.
- **Running the scope check only before the pull
  request**, after several commits have built on a core
  change.

Reference: [infrahub-sync repository](https://github.com/opsmill/infrahub-sync)
