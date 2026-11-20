"""Fake ServiceNow Table API built from the captured responses.

It applies the rules in api-behavior.yml: sysparm_fields keeps only the named
fields and drops unknown names without an error, references keep their
captured shape, and a captured page is served with its headers unchanged.
"""

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

CAPTURES = Path(__file__).resolve().parents[1] / "fixtures" / "servicenow"


class FakeResponse:
    def __init__(self, status_code, headers, body):
        self.status_code = status_code
        self.headers = headers
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.captures = [json.loads(p.read_text()) for p in sorted(CAPTURES.glob("*.json"))]

    def get(self, url, params=None, headers=None, timeout=None):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        query.update(params or {})
        for cap in self.captures:
            cap_parts = urlsplit(cap["request"]["path"])
            if cap_parts.path == parts.path and dict(parse_qsl(cap_parts.query)) == query:
                return FakeResponse(cap["status"], dict(cap["headers"]), cap["body"])
        rows = {}
        for cap in self.captures:
            if urlsplit(cap["request"]["path"]).path == parts.path and cap["status"] == 200:
                for row in cap["body"]["result"]:
                    rows.setdefault(row["sys_id"], row)
        rows = list(rows.values())
        fields = [f for f in query.get("sysparm_fields", "").split(",") if f]
        if fields:
            rows = [{f: r[f] for f in fields if f in r} for r in rows]
        offset = int(query.get("sysparm_offset", 0))
        limit = int(query.get("sysparm_limit", 10000))
        page = rows[offset:offset + limit]
        link = ""
        if offset + limit < len(rows):
            nxt = dict(query, sysparm_offset=str(offset + limit))
            link = f'<{parts.scheme}://{parts.netloc}{parts.path}?{urlencode(nxt, safe=",^")}>;rel="next"'
        return FakeResponse(200, {"Link": link, "X-Total-Count": str(len(rows))}, {"result": page})


def make_fake_session():
    return FakeSession()
