"""Every task grader in eval.yaml must run in the layout skillgrade gives it.

skillgrade copies graders/ and skills/ into a temporary trial directory and
runs each grader's `run:` line from there. Nothing else from the repo is
present, eval.yaml included. A grader that crashes in that layout scores
every trial 0.0 regardless of what the agent did, and the only signal is a
traceback inside the eval results artifact.

Three graders did this on main for weeks: two managing-schemas task graders
called a `run_checks` signature that a merge had dropped, and the
reporting-skill-gaps redaction grader read eval.yaml at grade time. The unit
tests imported their check functions directly, so none of them ran the
script the eval runs.
"""

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EVAL_YAML = _REPO_ROOT / "eval.yaml"


def _grader_commands() -> list[tuple[str, str]]:
    """Return (task name, run line) for every deterministic grader."""
    config = yaml.safe_load(_EVAL_YAML.read_text())
    commands = []
    for task in config.get("tasks", []):
        for grader in task.get("graders", []):
            if grader.get("type") == "deterministic" and grader.get("run"):
                commands.append((task["name"], grader["run"]))
    return commands


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A trial directory holding only what skillgrade copies, and no output."""
    root = tmp_path_factory.mktemp("skillgrade-sandbox")
    shutil.copytree(_REPO_ROOT / "graders", root / "graders")
    shutil.copytree(_REPO_ROOT / "skills", root / "skills")
    return root


@pytest.mark.parametrize(
    ("task", "run"), _grader_commands(), ids=[t for t, _ in _grader_commands()]
)
def test_grader_runs_in_sandbox(sandbox: Path, task: str, run: str) -> None:
    """With no agent output, the grader exits cleanly and scores without errors.

    An empty trial is the one input every grader must handle, so it is the
    cheapest way to reach each script's `__main__` without a fixture per task.
    """
    argv = shlex.split(run)
    assert argv[0] == "python", f"{task}: unexpected interpreter in {run!r}"
    result = subprocess.run(
        [sys.executable, *argv[1:]],
        cwd=sandbox,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"{task}: `{run}` exited {result.returncode}\n"
        f"stderr:\n{result.stderr[-2000:]}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    assert isinstance(payload, dict), (
        f"{task}: `{run}` printed no JSON object (exit {result.returncode})\n"
        f"stderr:\n{result.stderr[-2000:]}"
    )
    assert "score" in payload, f"{task}: grader JSON has no score: {payload}"
    check_errors = [
        check for check in payload.get("checks", [])
        if "Error running check:" in check.get("message", "")
    ]
    assert not check_errors, f"{task}: grader swallowed check errors: {check_errors}"


def test_redaction_seeds_match_eval_prompt() -> None:
    """The redaction grader's seeded identifiers all appear in its task prompt.

    This guard used to run inside the grader, where eval.yaml is absent. It
    runs in a subprocess because the grader imports its sibling as `lib`,
    a name every skill's grader directory shares.
    """
    script = (
        "import check_no_customer_data as g; "
        "g._verify_seeds_against_eval_yaml(g.SEEDED_IDENTIFIERS)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT / "graders" / "reporting-skill-gaps",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
