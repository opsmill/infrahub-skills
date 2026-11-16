"""Tests for the trace checks in graders/analyzing-diagnostics/lib.py.

Two task graders grade rules/triage-traces.md, each against the fixtures of
its folder under fixtures/analyzing-diagnostics/. The compliant cases must
score 1.0; the violating cases must score below 1.0 and fail on the check of
the rule, not on a neighbouring one.

traces_analysis (check_traces_analysis.py, check `traces-slow-span`): the task
gives trace 0001 of a real bundle, a "Sync Git Repositories" task on
infrahub-task-worker that took 10.74 s while its children took about 21 ms.

- pass: one paragraph names the span, the service and "10.74 s", and explains
  the self time.
- pass-variant: a table row with "10741 ms", and a `jq` script on the bundle
  file, which reads the bundle and calls no service.
- fail: sends the analysis to Tempo and Grafana and names nothing.
- fail-nearmiss: blames the API from the small spans; the slow span appears
  only in a `jq` block and its comment. A check that reads code blocks passes
  it.
- fail-nearmiss-split: names the span in one paragraph, and puts the 10.74 s
  on infrahub-server in another. A check that looks for the three values
  anywhere in the report passes it.
- fail-nearmiss-remote: a correct analysis, but it posts the traces to the
  customer's Tempo.
- fail-nearmiss-local-tempo: a correct analysis, but it starts a local Tempo
  and posts the traces to it. The skill reads the bundle files only (review of
  #243). A check that allows a local host passes it.

traces_missing (check_traces_missing.py, check `recommends-traces`): a
slowness that ended, and a bundle without a `traces` entry.

- pass: a next bundle with `--include-traces --traces-start --traces-end` in a
  code block, handed to infrahub-collecting-diagnostics.
- pass-variant: the same in prose, with the `=` form of the options.
- fail: asks only for `--include-queries`.
- fail-nearmiss: names `--include-traces` and both window options, but in a
  negated sentence. A check that ignores negation passes it.
- fail-nearmiss-since: `--include-traces --traces-since 2h` for a slowness
  that ended yesterday, so the window does not cover it. A check that accepts
  any window passes it.

Fixtures are `.txt` so rumdl does not reformat them.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "analyzing-diagnostics"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "analyzing-diagnostics"

# Load lib.py by path under a unique name: every grader directory has a lib.py.
_spec = importlib.util.spec_from_file_location(
    "analyzing_diagnostics_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# fixture folder -> (task grader script, the check of the rule)
TASKS = {
    "traces_analysis": ("check_traces_analysis.py", "traces-slow-span"),
    "traces_missing": ("check_traces_missing.py", "recommends-traces"),
}


def _task_checks(script: str) -> list:
    """The CHECKS list of a task grader, read without importing the script."""
    tree = ast.parse((_GRADER_DIR / script).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "CHECKS" for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{script} defines no CHECKS")


def _failed(result: dict) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["passed"]]


def _fixtures(prefix: str) -> list[tuple[str, str]]:
    pairs = [(task, f.stem) for task in sorted(TASKS) for f in sorted((_FIXTURES / task).glob(f"{prefix}*.txt"))]
    for task in TASKS:
        assert any(t == task for t, _ in pairs), f"{task} has no {prefix} fixture"
    return pairs


@pytest.mark.parametrize(("task", "fixture"), _fixtures("pass"))
def test_compliant_fixture_scores_full(task: str, fixture: str) -> None:
    script, _ = TASKS[task]
    result = _mod.run_checks(_task_checks(script), _FIXTURES / task / f"{fixture}.txt")
    assert result["score"] == 1.0, result["details"]


@pytest.mark.parametrize(("task", "fixture"), _fixtures("fail"))
def test_violating_fixture_fails_on_the_rule(task: str, fixture: str) -> None:
    script, check = TASKS[task]
    result = _mod.run_checks(_task_checks(script), _FIXTURES / task / f"{fixture}.txt")
    assert result["score"] < 1.0, result["details"]
    failed = _failed(result)
    assert len(failed) == 1 and failed[0].startswith(check), result["details"]


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


@pytest.mark.parametrize(
    "command",
    [
        'curl -H "Accept: application/json" http://localhost:3200/api/v2/traces/6c26f0d2',
        "curl 'http://localhost:3200/api/search?q={}'",
        "docker run -d -p 3000:3000 grafana/grafana:11.4.0",
    ],
)
def test_any_trace_service_call_fails(command: str) -> None:
    """Querying a Tempo, even a local one, or starting Grafana fails (review of #243)."""
    text = f"Sync Git Repositories on infrahub-task-worker took 10.74 s.\n\n```bash\n{command}\n```\n"
    ok, msg = _mod.check_traces_slow_span(text, **_KWARGS)
    assert not ok and "trace service" in msg, msg


def test_trace_service_in_a_comment_does_not_count() -> None:
    """A shell comment that names a Tempo URL runs nothing."""
    text = (
        "Sync Git Repositories on infrahub-task-worker took 10.74 s.\n\n```bash\n"
        "jq . bundle/traces/0001.json  # not curl http://localhost:4318/v1/traces\n```\n"
    )
    ok, msg = _mod.check_traces_slow_span(text, **_KWARGS)
    assert ok, msg


@pytest.mark.parametrize(
    ("report", "window", "expected"),
    [
        ("Collect again with `--include-traces --traces-since 2h`.", "any", True),
        ("Collect again with `--include-traces --traces-since 2h`.", "absolute", False),
        ("Collect again with `--include-traces --traces-start X --traces-end Y`.", "absolute", True),
        # The window options are in another paragraph.
        ("Collect again with `--include-traces`.\n\nUse `--traces-start X --traces-end Y`.", "absolute", False),
        ("Do not add `--include-traces --traces-start X --traces-end Y`.", "absolute", False),
        ("There is no need for `--include-traces --traces-start X --traces-end Y`.", "absolute", False),
    ],
)
def test_recommends_traces(report: str, window: str, expected: bool) -> None:
    ok, msg = _mod.check_recommends_traces(report, window=window)
    assert ok is expected, msg
