"""Tests for the trace checks in graders/analyzing-diagnostics/lib.py.

The task grader check_traces_analysis.py runs against the fixtures under
fixtures/analyzing-diagnostics/traces_analysis/. The compliant cases must
score 1.0; the violating cases must score below 1.0 and fail on
`traces-slow-span`, the check that grades rules/triage-traces.md.

The task gives trace 0001 of a real bundle: a "Sync Git Repositories" task on
infrahub-task-worker that took 10.74 s, while its children (a database query
and a POST to infrahub-server) took about 21 ms.

What each fixture guards against:

- pass: one paragraph names the span, the service and "10.74 s", and explains
  the self time.
- pass-variant: a table row with "10741 ms", and a replay to a local Tempo,
  which the rule allows for a person who wants a timeline.
- fail: sends the analysis to Tempo and Grafana and names nothing.
- fail-nearmiss: blames the API from the small spans; the slow span appears
  only in a `jq` block and its comment. A check that reads code blocks passes
  it.
- fail-nearmiss-split: names the span in one paragraph, and puts the 10.74 s
  on infrahub-server in another. A check that looks for the three values
  anywhere in the report passes it.
- fail-nearmiss-remote: a correct analysis, but it posts the traces to the
  customer's Tempo.

Fixtures are `.txt` so rumdl does not reformat them.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "analyzing-diagnostics"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "analyzing-diagnostics" / "traces_analysis"

# Load lib.py by path under a unique name: every grader directory has a lib.py.
_spec = importlib.util.spec_from_file_location(
    "analyzing_diagnostics_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _task_checks() -> list:
    """The CHECKS list of check_traces_analysis.py, read without importing the script."""
    tree = ast.parse((_GRADER_DIR / "check_traces_analysis.py").read_text())
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "CHECKS" for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError("check_traces_analysis.py defines no CHECKS")


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
    assert len(failed) == 1 and failed[0].startswith("traces-slow-span"), result["details"]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("curl -X POST http://localhost:4318/v1/traces --data-binary @bundle/traces/0001-a.json", True),
        ('curl http://localhost:4318/v1/traces -d @"$f"', True),
        ("curl http://localhost:4318/v1/traces --data-binary=@bundle/traces/0001-a.json", True),
        # No file of traces/ is sent.
        ("curl -X POST http://localhost:4318/v1/traces -d '{\"resourceSpans\": []}'", False),
        # Another endpoint.
        ("curl -X POST http://localhost:4318/v1/logs --data-binary @bundle/traces/0001-a.json", False),
    ],
)
def test_posts_trace_file(command: str, expected: bool) -> None:
    commands = _mod._curl_commands(f"```bash\n{command}\n```\n")
    assert any(_mod._posts_trace_file(c) for c in commands) is expected, commands


_KWARGS = {
    "span": "Sync Git Repositories",
    "service": "infrahub-task-worker",
    "duration": r"10[.,]7\d*\s*(s|sec|seconds)\b|107\d\d(\.\d+)?\s*ms\b",
}


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ("Sync Git Repositories on infrahub-task-worker took 10.74 s.", True),
        ("Sync Git Repositories on infrahub-task-worker took 10.7 seconds.", True),
        ("Sync Git Repositories on infrahub-task-worker took 10741.2 ms.", True),
        # Another duration: the check reads the duration, not only the names.
        ("Sync Git Repositories on infrahub-task-worker took 19.7 ms.", False),
        # 107 s is not 10.7 s.
        ("Sync Git Repositories on infrahub-task-worker took 107 s.", False),
    ],
)
def test_slow_span_reads_the_duration(report: str, expected: bool) -> None:
    ok, msg = _mod.check_traces_slow_span(f"bundle_information.json\n\n{report}\n", **_KWARGS)
    assert ok is expected, msg


def test_replay_to_another_remote_host_fails() -> None:
    """Any host that is not local fails, not only the customer's Tempo."""
    text = (
        "Sync Git Repositories on infrahub-task-worker took 10.74 s.\n\n```bash\n"
        "curl -X POST https://tempo.opsmill-shared.example/v1/traces --data-binary @bundle/traces/0001-a.json\n"
        "```\n"
    )
    ok, msg = _mod.check_traces_slow_span(text, **_KWARGS)
    assert not ok and "not to a local Tempo" in msg, msg
