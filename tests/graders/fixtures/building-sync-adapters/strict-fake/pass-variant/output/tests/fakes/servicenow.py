import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

_DIR = Path(__file__).parent.parent / "fixtures" / "servicenow"


def _load(name):
    return json.loads((_DIR / name).read_text())


def _select(row, wanted):
    return {k: v for k, v in row.items() if not wanted or k in wanted}


def _respond(status, headers, body):
    return SimpleNamespace(status_code=status, headers=headers, json=lambda: body)


def make_fake_session():
    page = _load("cmdb_ci_netgear_page1.json")
    page_query = dict(parse_qsl(urlsplit(page["request"]["path"]).query))

    def get(url, params=None, headers=None, timeout=None):
        query = {**dict(parse_qsl(urlsplit(url).query)), **(params or {})}
        if query == page_query:
            return _respond(page["status"], page["headers"], page["body"])
        same_page = {k: v for k, v in query.items() if k != "sysparm_fields"} == {
            k: v for k, v in page_query.items() if k != "sysparm_fields"
        }
        if not same_page:
            return _respond(404, {}, {"error": {"message": "no capture for this page"}})
        wanted = set(filter(None, query.get("sysparm_fields", "").split(",")))
        rows = [_select(r, wanted) for r in page["body"]["result"]]
        return _respond(200, {"X-Total-Count": str(len(rows))}, {"result": rows})

    return SimpleNamespace(get=get)
