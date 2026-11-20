from types import SimpleNamespace

ROWS = [
    {"sys_id": "abc123", "name": "core-sw-01", "location": {"link": "x", "value": "loc1"}},
    {"sys_id": "def456", "name": "edge-rtr-01", "location": ""},
]


def make_fake_session():
    def get(url, params=None, headers=None, timeout=None):
        fields = (params or {}).get("sysparm_fields", "")
        wanted = set(fields.split(",")) if fields else None
        rows = [{k: v for k, v in r.items() if wanted is None or k in wanted} for r in ROWS]
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {"result": rows})

    return SimpleNamespace(get=get)
