"""Tests for the traces replay check in graders/analyzing-diagnostics/lib.py.

The task grader check_traces_replay.py runs against the fixtures under
fixtures/analyzing-diagnostics/traces_replay/. The compliant cases must score
1.0; the violating cases must score below 1.0 and fail on
`traces-replayed-by-id`, the check that grades rules/triage-traces.md.

What each fixture guards against:

- pass: a shell loop posts every file to localhost:4318/v1/traces, and the
  report opens the traces in Grafana by the trace ID in the file name.
- pass-variant: one curl call per file in a `console` block with a `$ `
  prompt, to 127.0.0.1, and the trace opened with the Tempo API
  `/api/v2/traces/<id>`.
- fail: reads the JSON files by hand and searches Grafana. No replay.
- fail-nearmiss: replays and opens by ID, but posts the traces to the
  customer's Tempo, the host of the manifest. A check that looks only for
  `/v1/traces` passes it.
- fail-nearmiss-search: replays into a local Tempo, then searches for the
  traces instead of opening them by ID. A search does not find replayed traces
  with old timestamps. A check that looks only for the replay passes it.

Fixtures are `.txt` so rumdl does not reformat them.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "analyzing-diagnostics"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "analyzing-diagnostics" / "traces_replay"

# Load lib.py by path under a unique name: every grader directory has a lib.py.
_spec = importlib.util.spec_from_file_location(
    "analyzing_diagnostics_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _task_checks() -> list:
    """The CHECKS list of check_traces_replay.py, read without importing the script."""
    tree = ast.parse((_GRADER_DIR / "check_traces_replay.py").read_text())
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "CHECKS" for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError("check_traces_replay.py defines no CHECKS")


def _failed(result: dict) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["passed"]]


def _fixtures(prefix: str) -> list[str]:
    names = sorted(f.stem for f in _FIXTURES.glob(f"{prefix}*.txt"))
    assert names, f"no {prefix} fixture"
    return names


@pytest.mark.parametrize("fixture", _fixtures("pass"))
def test_compliant_fixture_scores_full(fixture: str) -> None:
    result = _mod.run_checks(_task_checks(), _FIXTURES / f"{fixture}.txt")
    assert result["score"] == 1.0, result["details"]


@pytest.mark.parametrize("fixture", _fixtures("fail"))
def test_violating_fixture_fails_on_the_rule(fixture: str) -> None:
    result = _mod.run_checks(_task_checks(), _FIXTURES / f"{fixture}.txt")
    assert result["score"] < 1.0, result["details"]
    failed = _failed(result)
    assert len(failed) == 1 and failed[0].startswith("traces-replayed-by-id"), result["details"]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('curl -X POST http://localhost:4318/v1/traces --data-binary @bundle/traces/0001-a.json', True),
        ('curl http://localhost:4318/v1/traces -d @"$f"', True),
        ('curl http://localhost:4318/v1/traces --data-binary=@bundle/traces/0001-a.json', True),
        # No file of traces/ is sent.
        ('curl -X POST http://localhost:4318/v1/traces -d \'{"resourceSpans": []}\'', False),
        # Another endpoint.
        ("curl -X POST http://localhost:4318/v1/logs --data-binary @bundle/traces/0001-a.json", False),
    ],
)
def test_posts_trace_file(command: str, expected: bool) -> None:
    commands = _mod._curl_commands(f"```bash\n{command}\n```\n")
    assert any(_mod._posts_trace_file(c) for c in commands) is expected, commands


def test_replay_to_another_remote_host_fails() -> None:
    """Any host that is not local fails, not only the customer's Tempo."""
    text = (
        "Read bundle_information.json.\n\n```bash\n"
        "curl -X POST https://tempo.opsmill-shared.example/v1/traces --data-binary @bundle/traces/0001-a.json\n"
        "```\n\nOpen it by the trace ID in its file name.\n"
    )
    ok, msg = _mod.check_traces_replayed_by_id(text, customer_host="tempo.monitoring.acme.internal")
    assert not ok and "not to a local Tempo" in msg, msg


def test_negated_trace_id_does_not_count() -> None:
    """ "You do not need the trace ID" does not open the traces by ID."""
    text = (
        "```bash\ncurl -X POST http://localhost:4318/v1/traces --data-binary @bundle/traces/0001-a.json\n```\n\n"
        "You do not need the trace ID: search for traces longer than 1s.\n"
    )
    ok, msg = _mod.check_traces_replayed_by_id(text)
    assert not ok and "by trace ID" in msg, msg
