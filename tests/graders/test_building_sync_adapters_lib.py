"""Four-fixture runs for every task grader of infrahub-building-sync-adapters.

Each task has a compliant answer, a compliant variant written the way the
check's traversal is most likely to miss, an obvious violation, and a near
miss that keeps the rule's vocabulary while breaking it. The task scripts run
as skillgrade runs them, from the fixture directory, so the test covers the
script and the library together.
"""

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
        (
            "- `infrahub-sync list --directory examples/`: lists from-servicenow\n",
            "infrahub-sync list",
        ),
        ("Docs page `docs/docs/adapters/servicenow.mdx`, ", "docs page"),
        (
            ", row in `docs/docs/adapters/choosing-an-adapter.mdx`",
            "choosing-an-adapter row",
        ),
        ("`docs/docs/readme.mdx`, ", "docs readme list"),
        ("`README.md` and ", "README.md list"),
        (" and `AGENTS.md`", "AGENTS.md list"),
    ],
)
def test_pr_checks_require_every_docs_item(dropped: str, item: str) -> None:
    text = _PASS_PR.read_text()
    assert dropped in text
    ok, details = lib.check_pr_checks_complete({"pr_text": text.replace(dropped, "")})
    assert not ok
    assert item in details


def test_pr_checks_require_a_result_after_each_command() -> None:
    """Only the code spans, with no result after them, is a list of checks not run."""
    text = _PASS_PR.read_text()
    bare = "\n".join(
        line.split(": ", 1)[0] if line.startswith("- `") else line
        for line in text.splitlines()
    )
    ok, details = lib.check_pr_checks_complete({"pr_text": bare})
    assert not ok
    assert "no result written after" in details


@pytest.mark.parametrize("heading", ["## Tests added", "## Latest changes"])
def test_pr_checks_prefer_the_checks_run_heading(heading: str) -> None:
    """A heading that names tests, or holds "test" inside a word, comes before
    `## Checks run` and must not hide it."""
    text = _PASS_PR.read_text().replace(
        "## Checks run",
        f"{heading}\n\n- `tests/adapters/test_servicenow.py`\n\n## Checks run",
    )
    ok, details = lib.check_pr_checks_complete({"pr_text": text})
    assert ok, details


def test_pr_checks_need_a_result_for_commands_joined_with_and() -> None:
    """All the commands on one line, joined with "and", and no result."""
    text = _PASS_PR.read_text()
    commands = [
        line[2:].split(": ", 1)[0]
        for line in text.splitlines()
        if line.startswith("- `") and ("uv run" in line or "infrahub-sync" in line)
    ]
    body = text.split("## Checks run", 1)
    rest = [line for line in body[1].splitlines() if not line.startswith("- `")]
    joined = (
        body[0]
        + "## Checks run\n\n- "
        + " and ".join(commands)
        + "\n"
        + "\n".join(rest)
    )
    ok, details = lib.check_pr_checks_complete({"pr_text": joined})
    assert not ok
    assert "no result written after" in details


def test_pr_checks_accept_a_status_mark_and_a_grouped_result() -> None:
    text = _PASS_PR.read_text()
    marked = (
        text.replace("`uv run ty check .`: passed", "`uv run ty check .`: \u2705")
        .replace("- `uv run rumdl check .`: passed\n", "")
        .replace(
            "`uv run invoke format`: no changes",
            "`uv run invoke format` and `uv run rumdl check .`: no changes",
        )
    )
    ok, details = lib.check_pr_checks_complete({"pr_text": marked})
    assert ok, details


def test_pr_checks_ignore_commands_that_are_only_printed() -> None:
    text = _PASS_PR.read_text().replace(
        "`uv run ty check .`: passed", "`echo uv run ty check .`: printed"
    )
    ok, details = lib.check_pr_checks_complete({"pr_text": text})
    assert not ok
    assert "type check" in details


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
_RETRY_CHECKS = (
    "retry-status-set",
    "retry-after-honored",
    "retry-after-cap",
    "backoff-capped-jitter",
    "no-tls-retry",
    "shared-retry-budget",
)


def _retry_checks(tmp_path: Path, source: str) -> dict[str, bool]:
    (tmp_path / "servicenow_client.py").write_text(source)
    ctx = lib.build_context(tmp_path)
    return {name: lib.CHECKS[name](ctx)[0] for name in _RETRY_CHECKS}


# Each mutation of the compliant client keeps the rule's vocabulary (the status
# set, the header read, the comparison with 300, min(..., 60), random, SSLError)
# but changes what the client does. The review of #236 found each of these
# passing the earlier, AST-only checks.
_RETRY_MUTATIONS = {
    "status set defined, only 429 retried": (
        "if resp.status_code not in RETRY_STATUSES:",
        "if resp.status_code != 429:",
        "retry-status-set",
    ),
    "membership test reversed": (
        "if resp.status_code not in RETRY_STATUSES:",
        "if resp.status_code in RETRY_STATUSES:",
        "retry-status-set",
    ),
    "Retry-After read, fixed sleep": (
        "            time.sleep(wait)\n",
        "            time.sleep(5)\n",
        "retry-after-honored",
    ),
    "parsed wait overwritten": (
        "                wait = float(retry_after)\n",
        "                wait = float(retry_after)\n                wait = 5\n",
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
    "jitter added after the cap": (
        "return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
        "return min(BACKOFF_CAP, 2 ** attempt) + random.uniform(0, 5)",
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
    "TLS errors retried": (
        "            except requests.exceptions.SSLError:\n                raise\n",
        "",
        "no-tls-retry",
    ),
    "timeouts not retried": (
        "except (requests.ConnectionError, requests.Timeout):",
        "except requests.ConnectionError:",
        "no-tls-retry",
    ),
    "a second budget for connection errors": (
        "            except (requests.ConnectionError, requests.Timeout):\n                attempt += 1\n"
        "                if attempt > self.max_retries:",
        "            except (requests.ConnectionError, requests.Timeout):\n                errors = getattr(self, 'errors', 0) + 1\n"
        "                self.errors = errors\n                if errors > self.max_retries:",
        "shared-retry-budget",
    ),
    # Review of PR #236: two budgets of different sizes.
    "a larger budget for connection errors": (
        "            except (requests.ConnectionError, requests.Timeout):\n                attempt += 1\n"
        "                if attempt > self.max_retries:",
        "            except (requests.ConnectionError, requests.Timeout):\n"
        "                self.conn_attempt = getattr(self, 'conn_attempt', 0) + 1\n"
        "                if self.conn_attempt > 15:",
        "shared-retry-budget",
    ),
    # Review of PR #236: a jitter factor above 1 lifts the capped value past 60 s.
    "jitter factor above 1": (
        "random.uniform(0.5, 1.0)",
        "random.uniform(0.5, 1.5)",
        "backoff-capped-jitter",
    ),
    # Review of PR #236: the name is capped, then rebound to a value above the cap.
    "jitter added to the capped name": (
        "        return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
        "        delay = min(BACKOFF_CAP, 2 ** attempt)\n"
        "        delay = delay + random.uniform(0, 30)\n"
        "        return delay",
        "backoff-capped-jitter",
    ),
    "capped on one branch only": (
        "        return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
        "        if attempt > 3:\n"
        "            delay = 2 ** attempt * random.uniform(0.5, 1.0)\n"
        "        else:\n"
        "            delay = min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)\n"
        "        return delay",
        "backoff-capped-jitter",
    ),
}

# Compliant clients written another way: every retry check passes.
_RETRY_PASS_VARIANTS = {
    "random imported under an alias": (
        ("import random\n", "import random as rng\n"),
        ("random.uniform(0.5, 1.0)", "rng.uniform(0.5, 1.0)"),
    ),
    "uniform imported under an alias": (
        ("import random\n", "from random import uniform as draw\n"),
        ("random.uniform(0.5, 1.0)", "draw(0.5, 1.0)"),
    ),
    "capped by an if, in statement order": (
        (
            "        return min(BACKOFF_CAP, 2 ** attempt) * random.uniform(0.5, 1.0)",
            "        delay = 2 ** attempt * random.uniform(0.5, 1.0)\n"
            "        if delay > BACKOFF_CAP:\n"
            "            delay = BACKOFF_CAP\n"
            "        return delay",
        ),
    ),
}


def test_retry_checks_pass_the_compliant_client(tmp_path: Path) -> None:
    assert all(_retry_checks(tmp_path, _RETRY_PASS).values())


@pytest.mark.parametrize("case", list(_RETRY_PASS_VARIANTS))
def test_retry_checks_pass_a_compliant_variant(tmp_path: Path, case: str) -> None:
    source = _RETRY_PASS
    for old, new in _RETRY_PASS_VARIANTS[case]:
        assert source.count(old) == 1, f"the variant {case!r} no longer applies"
        source = source.replace(old, new)
    results = _retry_checks(tmp_path, source)
    assert all(results.values()), results


@pytest.mark.parametrize("case", list(_RETRY_MUTATIONS))
def test_retry_check_fails_when_the_behavior_breaks(tmp_path: Path, case: str) -> None:
    old, new, failing = _RETRY_MUTATIONS[case]
    assert _RETRY_PASS.count(old) == 1, f"the mutation for {case!r} no longer applies"
    results = _retry_checks(tmp_path, _RETRY_PASS.replace(old, new))
    assert results[failing] is False, results


def test_retry_probe_cannot_read_the_environment_or_spawn(tmp_path: Path) -> None:
    """Answer code runs with an empty environment and cannot start a process."""
    source = _RETRY_PASS + (
        "\nimport os, subprocess\n"
        "LEAK = os.environ.get('ANTHROPIC_API_KEY')\n"
        "assert LEAK is None, 'the environment reached the answer code'\n"
        "subprocess.run(['true'])\n"
    )
    (tmp_path / "servicenow_client.py").write_text(source)
    report = lib.run_probe("_retry_probe.py", tmp_path)
    assert "PermissionError" in report.get("error", ""), report


def test_retry_probe_refuses_writes_outside_the_answer_directory(
    tmp_path: Path,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    target = tmp_path / "outside.txt"
    (work / "servicenow_client.py").write_text(
        _RETRY_PASS + f"\nopen({str(target)!r}, 'w').write('x')\n"
    )
    report = lib.run_probe("_retry_probe.py", work)
    assert "PermissionError" in report.get("error", ""), report
    assert not target.exists()


_OUTSIDE_CHANGES = {
    "truncate": "os.truncate(OUT, 0)",
    "chmod": "os.chmod(OUT, 0o600)",
    "rename out": "open(IN, 'w').close(); os.rename(IN, OUT + '.moved')",
    "replace over": "open(IN, 'w').close(); os.replace(IN, OUT)",
    "hard link": "os.link(OUT, IN)",
    "symlink": "os.symlink(IN, OUT + '.link')",
    "remove": "os.remove(OUT)",
    "relative to a directory descriptor": "os.mkdir('d', dir_fd=os.open(DIR, os.O_RDONLY))",
    "udp send": "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('127.0.0.1', 9))",
}


@pytest.mark.parametrize("case", list(_OUTSIDE_CHANGES))
def test_retry_probe_refuses_changes_outside_the_answer_directory(
    tmp_path: Path, case: str
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    before = sorted(p.name for p in tmp_path.iterdir())
    prelude = (
        f"\nimport os\nOUT = {str(outside)!r}\nIN = {str(work / 'inside.txt')!r}\n"
        f"DIR = {str(tmp_path)!r}\n"
    )
    (work / "servicenow_client.py").write_text(
        _RETRY_PASS + prelude + _OUTSIDE_CHANGES[case] + "\n"
    )
    report = lib.run_probe("_retry_probe.py", work)
    assert "PermissionError" in report.get("error", ""), report
    assert outside.read_text() == "keep"
    assert oct(outside.stat().st_mode & 0o777) != oct(0o600)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def _selected(rows: list[dict]) -> dict:
    return {"probe": {"selected": {"status": 200, "rows": rows, "next": None}}}


def test_fake_serves_captures_compares_every_row() -> None:
    page = lib._captured_page()
    rows = [{f: r[f] for f in ("sys_id", "name")} for r in page]
    ok, details = lib.check_fake_serves_captures(_selected(rows))
    assert ok, details

    for wrong in (
        [rows[0], {"sys_id": "0" * 32, "name": "made-up"}],  # a made-up row
        [{**rows[0], "name": "renamed"}, rows[1]],  # a changed value
        [rows[0]],  # a row missing
        [{"sys_id": r["sys_id"]} for r in rows],  # a selected field dropped
        list(reversed(rows)),  # another order
        [],
    ):
        ok, details = lib.check_fake_serves_captures(_selected(wrong))
        assert not ok, wrong


def test_fake_next_link_fails_when_the_next_page_is_page_one() -> None:
    page = lib._captured_page()
    probe = {
        "captured_page": {
            "status": 200,
            "rows": page,
            "next": "n",
            "expected_next": "n",
        },
        "next_page": {"status": 200, "rows": page, "next": "n"},
    }
    ok, details = lib.check_fake_next_link({"probe": probe})
    assert not ok
    assert "first page again" in details
    probe["next_page"] = {"status": 404, "rows": [], "next": None}
    ok, details = lib.check_fake_next_link({"probe": probe})
    assert ok, details


@pytest.mark.parametrize(
    "other",
    [
        "docs/unrelated.mdx",
        "examples/netbox_to_infrahub/config.yml",
        "tests/adapters/test_netbox.py",
        ".github/workflows/ci.yml",
    ],
)
def test_scope_rejects_files_of_other_adapters_or_the_repository(
    tmp_path: Path, other: str
) -> None:
    root = tmp_path / "output"
    for rel in (
        "infrahub_sync/adapters/servicenow.py",
        "tests/adapters/test_servicenow.py",
        "docs/docs/adapters/servicenow.mdx",
        other,
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("")
    ok, details = lib.check_diff_stays_in_adapter({"output_dir": root})
    assert not ok
    assert other in details


# Each near-miss carries the rule's vocabulary and breaks one thing, so exactly
# the checks named here fail. A near-miss that fails everything proves nothing.
NEARMISS_FAILS = {
    "probe-behavior-file": {"behavior-next-link"},
    "strict-fake": {"fake-next-link"},
    "retry-policy": {"no-tls-retry"},
}


@pytest.mark.parametrize("task", list(NEARMISS_FAILS))
def test_nearmiss_fails_only_the_check_it_targets(task: str) -> None:
    result = _score(task, "fail-nearmiss")
    failed = {c["name"] for c in result["checks"] if not c["passed"]}
    assert failed == NEARMISS_FAILS[task], result["details"]


_BEHAVIOR_PASS = _FIXTURES / "probe-behavior-file" / "pass" / "api-behavior.yml"


def _behavior_checks(doc: dict) -> dict[str, bool]:
    ctx = {"behavior": doc}
    return {
        name: lib.CHECKS[name](ctx)[0]
        for name in (
            "behavior-keys",
            "behavior-covers-endpoints",
            "behavior-next-link",
            "behavior-rate-limit",
            "behavior-field-quirks",
        )
    }


def _netgear(doc: dict) -> dict:
    return next(e for e in doc["endpoints"] if e["path"].endswith("cmdb_ci_netgear"))


def _location(doc: dict) -> dict:
    return next(e for e in doc["endpoints"] if e["path"].endswith("cmn_location"))


# Each case is a wrong behavior file the review of #236 found passing.
_BEHAVIOR_MUTATIONS = {
    "POST instead of the captured GET": (
        lambda d: _netgear(d).update(method="POST"),
        "behavior-keys",
    ),
    "a scalar entry": (
        lambda d: d["endpoints"].append("cmdb_ci_netgear"),
        "behavior-keys",
    ),
    "a duplicate entry": (
        lambda d: d["endpoints"].append(dict(_netgear(d))),
        "behavior-covers-endpoints",
    ),
    "an endpoint matched by suffix": (
        lambda d: _netgear(d).update(path="/api/now/v2/table/cmdb_ci_netgear"),
        "behavior-covers-endpoints",
    ),
    "pagination type none despite the Link header": (
        lambda d: _netgear(d)["pagination"].update(type="none"),
        "behavior-next-link",
    ),
    "an extra next-link parameter": (
        lambda d: _netgear(d)["pagination"]["next_link_carries"].append("sysparm_view"),
        "behavior-next-link",
    ),
    "a 429 no capture shows": (
        lambda d: _location(d).update(
            rate_limit={"status": 429, "retry_after_header": True}
        ),
        "behavior-rate-limit",
    ),
    "the empty parent of the second location capture": (
        lambda d: _location(d)["field_quirks"].pop("reference_empty"),
        "behavior-field-quirks",
    ),
}


def test_behavior_checks_pass_the_compliant_file() -> None:
    doc = lib.yaml.safe_load(_BEHAVIOR_PASS.read_text())
    assert all(_behavior_checks(doc).values())


@pytest.mark.parametrize("case", list(_BEHAVIOR_MUTATIONS))
def test_behavior_check_fails_on_a_wrong_file(case: str) -> None:
    doc = lib.yaml.safe_load(_BEHAVIOR_PASS.read_text())
    mutate, failing = _BEHAVIOR_MUTATIONS[case]
    mutate(doc)
    assert _behavior_checks(doc)[failing] is False
