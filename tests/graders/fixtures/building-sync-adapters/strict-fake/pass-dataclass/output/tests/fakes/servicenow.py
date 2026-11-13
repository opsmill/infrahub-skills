"""Fake written with dataclasses, which resolve their module through sys.modules."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

_DIR = Path(__file__).parent.parent / "fixtures" / "servicenow"


@dataclass
class FakeResponse:
    status_code: int
    headers: dict
    body: dict

    def json(self):
        return self.body


@dataclass
class FakeSession:
    page: dict = field(default_factory=lambda: json.loads((_DIR / "cmdb_ci_netgear_page1.json").read_text()))

    def get(self, url, params=None, headers=None, timeout=None):
        query = {**dict(parse_qsl(urlsplit(url).query)), **(params or {})}
        if query == dict(parse_qsl(urlsplit(self.page["request"]["path"]).query)):
            return FakeResponse(self.page["status"], self.page["headers"], self.page["body"])
        wanted = {f for f in query.get("sysparm_fields", "").split(",") if f}
        rows = [{k: v for k, v in r.items() if not wanted or k in wanted} for r in self.page["body"]["result"]]
        return FakeResponse(200, {}, {"result": rows})


def make_fake_session():
    return FakeSession()
