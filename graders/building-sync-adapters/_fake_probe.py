"""Send prepared requests to a model-written ServiceNow fake and report what it returns.

Usage: python -I _fake_probe.py <output_dir> <captures_dir>

The fake lives at <output_dir>/tests/fakes/servicenow.py and exposes
``make_fake_session()``, whose result has ``get(url, params=None, headers=None,
timeout=None)`` returning an object with ``status_code``, ``headers`` and
``json()``. Network access is blocked before the module is imported, so a fake
that calls the real API fails instead of passing. The last stdout line is a
JSON report keyed by scenario.
"""

from __future__ import annotations

import importlib.util
import json
import re
import socket
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

BASE = "https://example.service-now.com/api/now/table/cmdb_ci_netgear"
HEADERS = {"Accept": "application/json"}


def _blocked(*_a, **_k):
    raise OSError("network access is blocked in the grader")


def _link_next(headers) -> str | None:
    value = None
    for key in list(getattr(headers, "keys", lambda: [])()):
        if str(key).lower() == "link":
            value = headers[key]
    links = dict(
        (rel, url)
        for url, rel in re.findall(r'<([^>]*)>\s*;\s*rel="([^"]+)"', value or "")
    )
    return links.get("next")


def _call(session, url, params=None):
    resp = session.get(url, params=params, headers=dict(HEADERS), timeout=10)
    body = resp.json()
    rows = body.get("result", []) if isinstance(body, dict) else []
    return {
        "status": int(resp.status_code),
        "rows": [r for r in rows if isinstance(r, dict)],
        "next": _link_next(resp.headers),
    }


def main() -> None:
    out_dir, captures_dir = Path(sys.argv[1]), Path(sys.argv[2])
    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.create_connection = _blocked  # type: ignore[assignment]
    report: dict = {}
    fake_path = out_dir / "tests" / "fakes" / "servicenow.py"
    if not fake_path.exists():
        print(json.dumps({"error": f"{fake_path.relative_to(out_dir)} not found"}))
        return
    sys.path[:0] = [str(out_dir), str(fake_path.parent)]
    try:
        spec = importlib.util.spec_from_file_location(
            "model_fake_servicenow", fake_path
        )
        module = importlib.util.module_from_spec(spec)
        # Register before executing, as a normal import does: dataclasses and
        # typing resolve the module through sys.modules while it runs.
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        session = module.make_fake_session()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"cannot build the fake: {exc!r}"}))
        return

    captured = json.loads((captures_dir / "cmdb_ci_netgear_page1.json").read_text())
    captured_url = "https://example.service-now.com" + captured["request"]["path"]
    expected_next = dict(
        (rel, url)
        for url, rel in re.findall(
            r'<([^>]*)>\s*;\s*rel="([^"]+)"', captured["headers"].get("Link", "")
        )
    ).get("next")

    # Vary only sysparm_fields: every other parameter is the captured request's,
    # so a fake that refuses filters it cannot evaluate is not penalised for it.
    base_params = dict(parse_qsl(urlsplit(captured_url).query))
    scenarios = {
        "selected": (BASE, {**base_params, "sysparm_fields": "sys_id,name"}),
        "unknown_field": (BASE, {**base_params, "sysparm_fields": "sys_id,nmae"}),
        "references": (BASE, base_params),
        "captured_page": (captured_url, None),
    }
    for name, (url, params) in scenarios.items():
        try:
            report[name] = _call(session, url, params)
        except Exception as exc:  # noqa: BLE001
            report[name] = {"error": f"{name}: the fake raised {exc!r}"}
    if "error" not in report["captured_page"]:
        report["captured_page"]["expected_next"] = expected_next
    print(json.dumps(report, default=str))


if __name__ == "__main__":
    main()
