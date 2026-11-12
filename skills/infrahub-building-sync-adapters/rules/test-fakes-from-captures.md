---
title: Build Test Fakes From the Captures and Enforce the Behavior File
impact: CRITICAL
description: >-
  Unit-test fakes serve the captured bodies and headers, not hand-written
  ones, and behave as api-behavior.yml records: field selection applied,
  unknown selected fields dropped with HTTP 200 when the file says so,
  reference shapes kept, next links served unchanged. Never looser or
  stricter than the real API.
tags: tests, fakes, captures, field-selection, pagination
---

## Build Test Fakes From the Captures and Enforce the Behavior File

The fake that stands in for the source API in unit
tests serves the captured responses and behaves the way
`api-behavior.yml` says the real API behaves. It is
neither looser nor stricter than the real API.

### Why it matters

A fake looser than the real API lets bugs through, and
a large test count hides them:

- **Microsoft Graph.** The fake returned every property
  whatever `$select` asked for. Two `$select` bugs, a
  filter and a transform reading properties the adapter
  never selected, passed 105 tests.
- **Webex.** The fake next-page links carried no
  `orgId`; the real links always do. The resulting bug
  passed 301 tests and stopped the first live run on
  page 2.

A fake stricter than the real API breaks the contract
the other way: it raises on a request the API accepts,
so the adapter gains error handling for an error that
never happens, and correct code fails its tests.

### How to apply

- **Serve the captures.** Load the redacted captures
  from `tests/fixtures/<name>/`. Do not write rows by
  hand; a hand-written row has the shapes you expect,
  not the ones the API sends.
- **Accept a full next-link URL.** The adapter follows
  the next link as a URL with its query string. Parse
  that query string and merge it with any `params`
  before choosing the page, then serve the captured page
  with its headers, the `Link` header included,
  unchanged.
- **Apply field selection** as `field_selection` names
  it: return only the selected fields.
- **Treat unknown selected fields as the file says.**
  With `unknown_selected_field: dropped_silently`, leave
  the unknown name out and still answer HTTP 200. Raise
  or return an error only when the file says `error`.
- **Keep reference shapes as captured.** An empty
  reference stays `""` when `reference_empty` is
  `empty_string`; a set one stays an object. Do not turn
  `""` into `None` in the fake.
- **Refuse what the real API refuses, and nothing
  more.** Check `required_headers` when the file lists a
  header beyond `Accept`. Do not reject a filter or a
  parameter the fake cannot evaluate; serve the captured
  page for the captured parameters instead.
- **Serve error captures on request.** A test that
  checks throttling queues the captured 429, with its
  `Retry-After` and reset headers, rather than writing a
  new one.

### Correct

A fake for an invented inventory API whose behavior file
records `field_selection: fields`, rows under `items`,
and `unknown_selected_field: dropped_silently`:

```python
"""Fake HTTP session for the netinventory adapter tests, built from the redacted captures."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "netinventory"
LIST_KEY = "items"  # where the rows sit in the captured body
SELECT_PARAM = "fields"  # api-behavior.yml: field_selection


class FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str], body: object) -> None:
        self.status_code = status_code
        self.headers = headers
        self._body = body

    def json(self) -> object:
        return self._body


def _query(url: str, params: dict | None) -> tuple[str, dict[str, str]]:
    """Path and parameters of a request, whether they arrive in the URL, in params, or both."""
    parts = urlsplit(url)
    merged = dict(parse_qsl(parts.query))
    merged.update({key: str(value) for key, value in (params or {}).items()})
    return parts.path.rstrip("/"), merged


def _page_key(path: str, params: dict[str, str]) -> tuple:
    """A page is the same page whatever fields were selected."""
    return path, tuple(sorted((k, v) for k, v in params.items() if k != SELECT_PARAM))


class FakeSession:
    def __init__(self, captures: list[dict]) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.queued: list[dict] = []  # error captures a test serves next: queued.append(errors[429])
        self.errors: dict[int, dict] = {}  # the captured error responses (429, 503), by status
        self._pages: dict[tuple, dict] = {}
        for capture in captures:
            if capture["status"] != 200:
                self.errors[capture["status"]] = capture
                continue
            path, params = _query(capture["request"]["path"], None)
            key = _page_key(path, params)
            # Two captures of one page: keep the one without field selection, it has every field.
            if key not in self._pages or SELECT_PARAM not in params:
                self._pages[key] = capture

    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float | None = None):
        path, merged = _query(url, params)
        self.requests.append((path, merged))
        if self.queued:
            capture = self.queued.pop(0)
            return FakeResponse(capture["status"], dict(capture["headers"]), capture["body"])
        capture = self._pages.get(_page_key(path, merged))
        if capture is None:
            return FakeResponse(404, {}, {"error": f"no capture for {path} {merged}"})
        body = capture["body"]
        selected = [name for name in merged.get(SELECT_PARAM, "").split(",") if name]
        if selected:
            # unknown_selected_field: dropped_silently -> a name the row lacks is left out, still HTTP 200.
            rows = [{name: row[name] for name in selected if name in row} for row in body[LIST_KEY]]
            body = {**body, LIST_KEY: rows}
        # Headers, the Link header included, go back exactly as captured.
        return FakeResponse(capture["status"], dict(capture["headers"]), body)


def make_fake_session() -> FakeSession:
    captures = [json.loads(path.read_text()) for path in sorted(FIXTURES.glob("*.json"))]
    return FakeSession(captures)
```

If the adapter reads headers in a different case than
the capture stores them, wrap them in
`requests.structures.CaseInsensitiveDict`, as a real
response does.

### Incorrect

Hand-written rows, every field returned whatever the
request selects, an error on an unknown field the real
API ignores, and a next link built without the
parameters the real link carries:

```python
class FakeSession:
    ROWS = [{"id": "1", "name": "edge-01", "site": None}]

    def get(self, url, params=None, headers=None, timeout=None):
        fields = (params or {}).get("fields", "")
        if "nmae" in fields:
            raise ValueError("unknown field")
        return FakeResponse(200, {"Link": '<https://inventory.example.net/api/v2/devices?offset=1>; rel="next"'},
                            {"items": self.ROWS})
```

### Common mistakes

- **Ignoring the query string of the URL** the adapter
  passes when it follows a next link, and so serving the
  first page again, or nothing.
- **Returning every captured field** whatever the field
  selection asks for. That is the Graph `$select` bug.
- **Raising on an unknown selected field** when the
  captures show HTTP 200.
- **Building next links by hand** without the parameters
  `next_link_carries` lists. That is the Webex `orgId`
  bug.
- **Cleaning up shapes**: `""` replaced by `None`, an
  object reference flattened to its ID.

Reference: [infrahub-sync repository](https://github.com/opsmill/infrahub-sync)
