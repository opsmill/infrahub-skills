---
title: Change Only the Adapter Files, and Draft Core Issues Instead
impact: HIGH
description: >-
  An adapter change touches only infrahub_sync/adapters/<name>.py plus its
  tests, example, docs, changelog fragment and spec, and the product names it
  adds to .vale/styles/spelling-exceptions.txt. Never edit other
  infrahub_sync files such as rest_api_client.py, utils.py, the core models or
  the loader: write a private helper in the adapter module and draft a core
  issue. Check with git diff --stat after each commit.
tags: scope, core, infrahub-sync, git, issue
---

## Change Only the Adapter Files, and Draft Core Issues Instead

An adapter change touches only these files in the
infrahub-sync checkout:

- `infrahub_sync/adapters/<name>.py`;
- its tests, `tests/adapters/test_<name>*.py`, and its
  fixtures under `tests/fixtures/<name>/`;
- its example under `examples/<name>*/`;
- its docs page `docs/docs/adapters/<name>.mdx`, and one
  line each in the adapter lists:
  `docs/docs/adapters/choosing-an-adapter.mdx`,
  `docs/docs/readme.mdx`, `docs/sidebars.ts`,
  `README.md` and `AGENTS.md`;
- the product names it adds to
  `.vale/styles/spelling-exceptions.txt`;
- its news fragment under `changelog/`;
- its spec under `dev/specs/<number>-<name>-adapter/`.

The merged Webex adapter (opsmill/infrahub-sync#401)
touched exactly these files.

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
- **After each commit, run the scope check.** It lists
  every changed file outside the list above, and must
  print nothing:

```bash
NAME="<name>"   # the adapter name
git diff --name-only "<base>" | grep -vE "^(infrahub_sync/adapters/$NAME\.py|tests/adapters/test_$NAME[^/]*\.py|tests/fixtures/$NAME/.+|examples/$NAME[^/]*/.+|docs/docs/adapters/($NAME|choosing-an-adapter)\.mdx|docs/docs/readme\.mdx|docs/sidebars\.ts|README\.md|AGENTS\.md|\.vale/styles/spelling-exceptions\.txt|changelog/[^/]+\.md|dev/specs/[^/]*-$NAME-[^/]*/.+)$"
```

`<base>` is the commit the adapter branch started from,
for example the output of
`git merge-base HEAD origin/main`. A line under
`infrahub_sync/` is a core file to revert; any other line
is a file of another adapter or of the repository, to
revert or to explain to the user. A drafted core issue
stays untracked, so it does not show here.

### Correct

The pagination helper lives in the adapter module, and a
core issue proposes the shared version:

```python
# infrahub_sync/adapters/netinventory.py
import re

# One link value: <url> then its parameters, where a quoted string may hold "," or ";".
_LINK = re.compile(r'<([^>]*)>((?:[^,"<]|"[^"]*")*)')
_PARAM = re.compile(r';\s*([^=;\s]+)\s*=\s*("[^"]*"|[^;]*)')


def _next_link(link_header: str | None) -> str | None:
    """The rel="next" URL of a Link header, selected exactly (never prev or last), whatever the parameter order."""
    for url, params in _LINK.findall(link_header or ""):
        for name, value in _PARAM.findall(params):
            if name.lower() == "rel" and "next" in value.strip().strip('"').lower().split():
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
