"""Four-fixture runs for every task grader of infrahub-building-sync-adapters.

Each task has a compliant answer, a compliant variant written the way the
check's traversal is most likely to miss, an obvious violation, and a near
miss that keeps the rule's vocabulary while breaking it. The task scripts run
as skillgrade runs them, from the fixture directory, so the test covers the
script and the library together.
"""

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADERS = _REPO_ROOT / "graders" / "building-sync-adapters"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "building-sync-adapters"

TASKS = {
    "probe-behavior-file": "check_probe_behavior_file.py",
    "strict-fake": "check_strict_fake.py",
    "pr-check-list": "check_pr_check_list.py",
    "retry-policy": "check_retry_policy.py",
    "identifiers-hfid": "check_identifiers_hfid.py",
    "scope-core-files": "check_scope_core_files.py",
}
CASES = [
    (task, fixture)
    for task in TASKS
    for fixture in ("pass", "pass-variant", "fail", "fail-nearmiss")
] + [("strict-fake", "pass-dataclass")]


def _score(task: str, fixture: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(_GRADERS / TASKS[task])],
        cwd=_FIXTURES / task / fixture,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize(("task", "fixture"), CASES)
def test_fixture_scores(task: str, fixture: str) -> None:
    result = _score(task, fixture)
    if fixture.startswith("pass"):
        assert result["score"] == 1.0, result["details"]
    else:
        assert result["score"] < 1.0, (
            f"{task}/{fixture} passed: the check does not discriminate"
        )


def test_fake_probe_blocks_network(tmp_path: Path) -> None:
    """A fake that calls the real API fails instead of passing."""
    fake = tmp_path / "output" / "tests" / "fakes" / "servicenow.py"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "import socket\n"
        "class S:\n"
        "    def get(self, url, params=None, headers=None, timeout=None):\n"
        "        socket.create_connection(('example.service-now.com', 443))\n"
        "def make_fake_session():\n"
        "    return S()\n"
    )
    proc = subprocess.run(
        [sys.executable, str(_GRADERS / TASKS["strict-fake"])],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    result = json.loads(proc.stdout)
    assert result["score"] == 0.0
    assert "blocked" in json.dumps(result)


# --------------------------------------------------------------------------
# Library checks: cases the four task fixtures do not reach
# --------------------------------------------------------------------------

# Loaded under its own name: every grader directory has a lib.py, and a bare
# ``import lib`` would shadow the other skills' modules for the whole session.
_lib_spec = importlib.util.spec_from_file_location(
    "building_sync_adapters_graders_lib", _GRADERS / "lib.py"
)
lib = importlib.util.module_from_spec(_lib_spec)
_lib_spec.loader.exec_module(lib)

_PASS_PR = _FIXTURES / "pr-check-list" / "pass" / "PR_DESCRIPTION.md"


@pytest.mark.parametrize(
    ("dropped", "item"),
    [
        ("- `infrahub-sync list --directory examples/`\n", "infrahub-sync list"),
        ("Docs page `docs/docs/adapters/servicenow.mdx`, ", "docs page"),
        (
            ", row in `docs/docs/adapters/choosing-an-adapter.mdx`",
            "choosing-an-adapter row",
        ),
    ],
)
def test_pr_checks_require_every_docs_item(dropped: str, item: str) -> None:
    text = _PASS_PR.read_text()
    assert dropped in text
    ok, details = lib.check_pr_checks_complete({"pr_text": text.replace(dropped, "")})
    assert not ok
    assert item in details


def test_identifiers_duplicate_mapping_does_not_hide_a_missing_kind() -> None:
    schema = {
        "nodes": [
            {
                "namespace": "Location",
                "name": "Site",
                "human_friendly_id": ["name__value"],
            },
            {
                "namespace": "Network",
                "name": "Device",
                "human_friendly_id": ["name__value"],
            },
        ]
    }
    config = {
        "schema_mapping": [
            {"name": "LocationSite", "identifiers": ["name"]},
            {"name": "LocationSite", "identifiers": ["name"]},
        ]
    }
    ok, details = lib.check_identifiers_match_hfid({"config": config, "schema": schema})
    assert not ok
    assert "NetworkDevice" in details


_TLS_CLIENT = """
import requests

def get(session, url):
    while True:
        try:
            return session.get(url)
        except requests.exceptions.SSLError:
            {ssl_body}
        except requests.exceptions.ConnectionError:
            continue
"""


@pytest.mark.parametrize(
    ("ssl_body", "expected"), [("raise", True), ("continue", False), ("pass", False)]
)
def test_no_tls_retry_requires_the_ssl_handler_to_reraise(
    ssl_body: str, expected: bool
) -> None:
    tree = ast.parse(_TLS_CLIENT.format(ssl_body=ssl_body))
    ok, details = lib.check_no_tls_retry({"py": tree, "py_err": None})
    assert ok is expected, details
