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
] + [("strict-fake", "pass-dataclass"), ("retry-policy", "pass-reset-guard")]


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


def test_fake_probe_without_output_dir_reports_an_error(tmp_path: Path) -> None:
    """A trial with no output/ fails the strict-fake checks with a message, not an exception."""
    report = lib.run_fake_probe(tmp_path / "output")
    assert "no " in report["error"]


def test_scope_ignores_caches_and_allows_vale_exceptions(tmp_path: Path) -> None:
    root = tmp_path / "output"
    for rel in (
        "infrahub_sync/adapters/servicenow.py",
        "infrahub_sync/adapters/__pycache__/servicenow.cpython-313.pyc",
        ".pytest_cache/v/cache/lastfailed",
        ".vale/styles/spelling-exceptions.txt",
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("")
    ok, details = lib.check_diff_stays_in_adapter({"output_dir": root})
    assert ok, details

    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("")
    ok, details = lib.check_diff_stays_in_adapter({"output_dir": root})
    assert not ok
    assert ".github/workflows/ci.yml" in details


_RETRY_PASS = (_FIXTURES / "retry-policy" / "pass" / "servicenow_client.py").read_text()


def _retry_checks(source: str) -> dict[str, bool]:
    ctx = {"py": ast.parse(source), "py_err": None}
    return {
        name: fn(ctx)[0]
        for name, fn in (
            ("retry-status-set", lib.check_retry_status_set),
            ("retry-after-honored", lib.check_retry_after_honored),
            ("retry-after-cap", lib.check_retry_after_cap),
            ("backoff-capped-jitter", lib.check_backoff_capped_jitter),
        )
    }


# Each mutation of the compliant client keeps the token the old check looked for
# (the status set, the header read, a comparison with 300, min(..., 60) and an
# import of random) but cuts it off from the value the client acts on.
_RETRY_MUTATIONS = {
    "status set defined, only 429 retried": (
        "if resp.status_code not in RETRY_STATUSES:",
        "if resp.status_code != 429:",
        "retry-status-set",
    ),
    "Retry-After read, fixed sleep": (
        "            time.sleep(wait)\n",
        "            time.sleep(5)\n",
        "retry-after-honored",
    ),
    "300 compared with the attempt count, not the wait": (
        "if wait > MAX_RETRY_AFTER:",
        "if attempt > MAX_RETRY_AFTER:",
        "retry-after-cap",
    ),
    "unrelated min(60) and a random call that does not reach the sleep": (
        "return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
        "limit = min(BACKOFF_CAP, self.max_retries)\n"
        "        random.seed(limit)\n"
        "        return 2 ** attempt",
        "backoff-capped-jitter",
    ),
    "jitter without a cap": (
        "return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
        "return 2 ** attempt * random.uniform(0.5, 1.0)",
        "backoff-capped-jitter",
    ),
    "cap without jitter": (
        "return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
        "return min(BACKOFF_CAP, 2 ** attempt)",
        "backoff-capped-jitter",
    ),
}


def test_retry_checks_pass_the_compliant_client() -> None:
    assert all(_retry_checks(_RETRY_PASS).values())


@pytest.mark.parametrize("case", list(_RETRY_MUTATIONS))
def test_retry_check_fails_when_the_value_does_not_drive_the_retry(case: str) -> None:
    old, new, failing = _RETRY_MUTATIONS[case]
    assert _RETRY_PASS.count(old) == 1, f"the mutation for {case!r} no longer applies"
    results = _retry_checks(_RETRY_PASS.replace(old, new))
    assert results == {name: name != failing for name in results}, results


def _selected(rows: list[dict]) -> dict:
    return {"probe": {"selected": {"status": 200, "rows": rows, "next": None}}}


def test_fake_serves_captures_compares_every_row() -> None:
    captured = list(lib._captured_rows("cmdb_ci_netgear").values())
    rows = [{f: r[f] for f in ("sys_id", "name")} for r in captured]
    ok, details = lib.check_fake_serves_captures(_selected(rows))
    assert ok, details

    made_up = [rows[0], {"sys_id": "0" * 32, "name": "made-up"}]
    ok, details = lib.check_fake_serves_captures(_selected(made_up))
    assert not ok
    assert "not in the captures" in details

    renamed = [{**rows[0], "name": "renamed"}, *rows[1:]]
    ok, details = lib.check_fake_serves_captures(_selected(renamed))
    assert not ok
    assert "captured" in details

    ok, details = lib.check_fake_serves_captures(_selected([]))
    assert not ok
