"""Fake built from the captured ServiceNow responses (sysparm_fields honoured by the adapter)."""

import json
from pathlib import Path
from types import SimpleNamespace

_DIR = Path(__file__).parent.parent / "fixtures" / "servicenow"
PAGE = json.loads((_DIR / "cmdb_ci_netgear_page1.json").read_text())


def make_fake_session():
    def get(url, params=None, headers=None, timeout=None):
        return SimpleNamespace(status_code=200, headers=PAGE["headers"], json=lambda: PAGE["body"])

    return SimpleNamespace(get=get)
