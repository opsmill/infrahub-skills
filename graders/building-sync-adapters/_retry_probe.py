"""Run a model-written retry client against scripted responses and report what it did.

Usage: python -I _retry_probe.py <workdir>

The client is ``<workdir>/servicenow_client.py``. The eval task asks for
``ServiceNowClient(session).get(url, params=None)``; when the module has no
such class, the probe takes the one class whose ``get`` it can call the same
way. Each scenario gives a fresh client a fake session that returns a scripted
list of responses and exceptions, then HTTP 200. ``time.sleep`` is replaced, so
the scenario records every wait instead of sleeping. The last stdout line is a
JSON report keyed by scenario: the number of requests, the waits, and how the
call ended.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import random
import sys
import time
from pathlib import Path

MAX_CALLS = 40


class _ProbeLimit(BaseException):  # noqa: N818 - not an error the client should catch
    """The client kept calling past MAX_CALLS: its retries have no bound."""


def _confine(workdir: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "_sandbox", Path(__file__).with_name("_sandbox.py")
    )
    sandbox = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sandbox)
    sandbox.confine(workdir)


def _response(requests, status: int, headers: dict | None = None):
    resp = requests.Response()
    resp.status_code = status
    resp.headers.update(headers or {})
    resp._content = b"{}"  # noqa: SLF001
    resp.url = "https://example.service-now.com/api/now/table/cmdb_ci_netgear"
    return resp


class _Session:
    """Returns the scripted outcomes in order, then HTTP 200."""

    def __init__(self, requests, script: list) -> None:
        self.requests = requests
        self.script = list(script)
        self.calls = 0

    def get(self, url, params=None, **_kwargs):
        self.calls += 1
        if self.calls > MAX_CALLS:
            raise _ProbeLimit
        outcome = self.script.pop(0) if self.script else 200
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, tuple):
            return _response(self.requests, *outcome)
        return _response(self.requests, outcome)

    request = None  # a client that calls session.request gets a TypeError, reported as a crash

    def mount(self, *_args, **_kwargs) -> None:
        pass


def _client_class(module):
    cls = getattr(module, "ServiceNowClient", None)
    if inspect.isclass(cls):
        return cls
    candidates = [
        obj
        for obj in vars(module).values()
        if inspect.isclass(obj)
        and obj.__module__ == module.__name__
        and callable(getattr(obj, "get", None))
    ]
    return candidates[0] if len(candidates) == 1 else None


def main() -> None:
    workdir = Path(sys.argv[1])
    path = workdir / "servicenow_client.py"
    if not path.exists():
        print(json.dumps({"error": "servicenow_client.py not found"}))
        return
    import requests  # imported before the sandbox, as the client will import it

    waits: list[float] = []

    def fake_sleep(seconds) -> None:
        waits.append(float(seconds))

    time.sleep = fake_sleep  # type: ignore[assignment]
    _confine(workdir)
    sys.path.insert(0, str(workdir))
    try:
        spec = importlib.util.spec_from_file_location("model_servicenow_client", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"cannot import servicenow_client.py: {exc!r}"}))
        return
    if getattr(module, "sleep", None) is not None and not inspect.isclass(module.sleep):
        module.sleep = fake_sleep  # `from time import sleep`
    cls = _client_class(module)
    if cls is None:
        print(
            json.dumps(
                {"error": "no ServiceNowClient class with a get(url, params) method"}
            )
        )
        return

    exc = requests.exceptions
    scenarios: dict[str, list] = {
        "ok": [200],
        "s429": [429],
        "s502": [502],
        "s503": [503],
        "s504": [504],
        "s500": [500],
        "s404": [404],
        "retry_after_30": [(429, {"Retry-After": "30"})],
        "retry_after_300": [(429, {"Retry-After": "300"})],
        "retry_after_301": [(429, {"Retry-After": "301"})],
        "retry_after_1422": [
            (429, {"Retry-After": "1422", "X-RateLimit-Reset": "1794420000"})
        ],
        "connection_error": [exc.ConnectionError("connection reset")],
        "timeout": [exc.ReadTimeout("read timed out")],
        "ssl_error": [exc.SSLError("certificate verify failed")],
        "always_503": [503] * (MAX_CALLS + 5),
        "always_connection_error": [exc.ConnectionError("down")] * (MAX_CALLS + 5),
        "mixed": [exc.ConnectionError("down"), 503] * (MAX_CALLS // 2 + 5),
    }
    report: dict = {}
    for name, script in scenarios.items():
        for seed in (1, 2) if name == "always_connection_error" else (1,):
            random.seed(seed)
            waits.clear()
            session = _Session(requests, script)
            entry: dict = {}
            try:
                result = cls(session).get(
                    "https://example.service-now.com/api/now/table/cmdb_ci_netgear"
                )
                entry["ended"] = "returned"
                entry["status"] = getattr(result, "status_code", None)
            except _ProbeLimit:
                entry["ended"] = "unbounded"
            except Exception as error:  # noqa: BLE001
                entry["ended"] = "raised"
                entry["exception"] = type(error).__name__
            entry["calls"] = min(session.calls, MAX_CALLS)
            entry["waits"] = list(waits)
            report[name if seed == 1 else f"{name}_seed{seed}"] = entry
    print(json.dumps(report))


if __name__ == "__main__":
    main()
