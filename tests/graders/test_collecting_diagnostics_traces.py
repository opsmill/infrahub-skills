"""Tests for the trace checks in graders/collecting-diagnostics/lib.py.

Each task grader runs against four fixtures under
fixtures/collecting-diagnostics/<task>/: compliant, compliant variant,
violating, and violating near miss. The two compliant cases must score 1.0;
the two violating cases must score below 1.0 and fail on the check that grades
rules/create-traces.md, not on a neighbouring one.

What each near miss guards against:

- traces_slowness: the full command with a window, a question about something
  else, and "traces?" only in a shell comment. A check that looks for any
  question, or reads comments, passes it.
- traces_reproducible: PUT and GET on the ratio endpoint, and "delete" in
  prose about the bundle folder. A check that matches the endpoint name or the
  word "delete" passes it.
- traces_no_terminal: names INFRAHUB_TRACES_API_TOKEN, but asks the operator
  to paste the token. A check that only looks for the variable passes it.
  fail-nearmiss-negation puts a "not" after the request ("Paste the token
  here; I will not log it."). A check that skips any sentence with a negation
  passes it (review of #234).
- basic_workflow: no trace option in any command, but a question that offers
  traces. A check that reads only the commands passes it.
  pass-stack-trace asks about a stack trace in the logs, which offers no
  traces. A check that matches any question with "trace" fails it (review
  of #234).

The compliant fixture of traces_slowness wraps its question over two lines,
which a line-by-line sentence split read as no question.

Fixtures are `.txt` so rumdl does not reformat them.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "collecting-diagnostics"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collecting-diagnostics"

# Load lib.py by path under a unique name: the task graders import it as
# `lib`, which would collide with every other grader's lib.py in sys.modules.
_spec = importlib.util.spec_from_file_location(
    "collecting_diagnostics_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks = _mod.run_checks


def _task_checks(task: str) -> list:
    """The CHECKS list a task grader runs, read without importing the script."""
    tree = ast.parse((_GRADER_DIR / f"check_{task}.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CHECKS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"check_{task}.py defines no CHECKS")


def _failed(result: dict) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["passed"]]


# task -> the check each violating fixture must fail on.
TASKS = {
    "traces_slowness": "traces-offered-with-window",
    "traces_reproducible": "ratio-raise-and-remove",
    "traces_no_terminal": "token-env-not-asked",
    "basic_workflow": "traces-not-offered",
}


def _fixtures(prefix: str) -> list[tuple[str, str]]:
    """Every (task, fixture) pair whose file name starts with the prefix.

    The four required fixtures are named pass, pass-variant, fail and
    fail-nearmiss; a review can add more under the same prefixes.
    """
    pairs = [
        (task, f.stem)
        for task in sorted(TASKS)
        for f in sorted((_FIXTURES / task).glob(f"{prefix}*.txt"))
    ]
    for task in TASKS:
        assert any(t == task for t, _ in pairs), f"{task} has no {prefix} fixture"
    return pairs


@pytest.mark.parametrize(("task", "fixture"), _fixtures("pass"))
def test_compliant_fixture_scores_full(task: str, fixture: str) -> None:
    result = run_checks(_task_checks(task), _FIXTURES / task / f"{fixture}.txt")
    assert result["score"] == 1.0, result["details"]


@pytest.mark.parametrize(("task", "fixture"), _fixtures("fail"))
def test_violating_fixture_fails_on_the_rule(task: str, fixture: str) -> None:
    result = run_checks(_task_checks(task), _FIXTURES / task / f"{fixture}.txt")
    assert result["score"] < 1.0, result["details"]
    assert _failed(result) == [TASKS[task]], result["details"]
