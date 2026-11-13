"""Every task grader in eval.yaml must run in the layout skillgrade gives it.

skillgrade copies graders/ into a temporary trial directory, puts every skill
under .claude/skills/ and .agents/skills/ (never under skills/), and runs each
grader's `run:` line from there. Nothing else from the repo is present,
eval.yaml included. A grader that crashes in that layout scores
every trial 0.0 regardless of what the agent did, and the only signal is a
traceback inside the eval results artifact.

Three graders did this on main for weeks: two managing-schemas task graders
called a `run_checks` signature that a merge had dropped, and the
reporting-skill-gaps redaction grader read eval.yaml at grade time. The unit
tests imported their check functions directly, so none of them ran the
script the eval runs.

Three more read a skill file from skills/ at grade time. The first version of
this test copied skills/ to the sandbox root and ran every grader on an empty
trial, so it passed them twice over: the path existed here and not in a real
trial, and the empty trial returned before the path was read.
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
    _copy_trial_layout(root)
    return root


def _copy_trial_layout(root: Path) -> None:
    """Lay out graders/ and the skills the way skillgrade's local provider does."""
    shutil.copytree(_REPO_ROOT / "graders", root / "graders")
    for discovery in (".claude/skills", ".agents/skills"):
        shutil.copytree(_REPO_ROOT / "skills", root / discovery)


_CRASH_MARKERS = ("Error running check:", "check crashed:")


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
        if any(marker in check.get("message", "") for marker in _CRASH_MARKERS)
    ]
    assert not check_errors, f"{task}: grader swallowed check errors: {check_errors}"


# An empty trial returns before any of these graders opens the skill file it
# reads, so each gets the smallest output that reaches that read.
_SEEDED_OUTPUT = {
    "graders/teaching-concepts/check_off_map.py": {
        ".infrahub-learning/lessons/webhooks.md": "## Probe\n\n## Explain\n\n## Exercise\n\n## Check\n",
    },
    "graders/teaching-concepts/check_graduation.py": {
        ".infrahub-learning/lessons/schema.md": "## Probe\n\n## Explain\n\n## Exercise\n\n## Check\n",
    },
    "graders/importing-data/check_self_check_rules.py": {
        "output_dir/answer.md": "Checked against format-structure.md.\n",
    },
}


@pytest.mark.parametrize("script", sorted(_SEEDED_OUTPUT))
def test_grader_reads_skill_files_in_trial_layout(
    tmp_path: Path, script: str
) -> None:
    """A grader that reads a skill file finds it where a trial puts it.

    No skills/ exists at the trial root, so a grader building its path from
    skills/ alone crashes or reports the file missing on every trial.
    """
    _copy_trial_layout(tmp_path)
    for rel, content in _SEEDED_OUTPUT[script].items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(content)
    run = next(r for _, r in _grader_commands() if r.split()[1] == script)
    result = subprocess.run(
        [sys.executable, *shlex.split(run)[1:]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    messages = [c.get("message", "") for c in json.loads(result.stdout).get("checks", [])]
    missing = [
        m for m in messages
        if any(marker in m for marker in _CRASH_MARKERS)
        or "not found at" in m
        or "could not read" in m
    ]
    assert not missing, f"{script}: skill file unreachable in trial layout: {missing}"


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
