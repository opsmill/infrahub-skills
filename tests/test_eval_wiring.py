"""Assert eval.yaml is wired to files that exist, in both directions.

Every task points at a skill that exists, and every task grader script under
`graders/` is run by some task.

Each task's instruction opens with `Read the skill at <path>`. A path to a
directory that does not exist still synced and still ran: `sync-evals.py`
pulls the skill name out with an unanchored regex, and `skillgrade` copies the
whole tree into the sandbox, so the model found the skill anyway. Two tasks
pointed at `.agents/skills/`, which holds only the contributor skills, and
nothing failed.

A task grader whose only call site is gone fails nothing either. One task ran
the generic `check_yagni_rule.py` while its bespoke script, the only place the
rule's cardinality assertion was wired, sat unreferenced on disk.
"""

from __future__ import annotations

import re
import shlex
from functools import cache
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent

SKILL_LINE = re.compile(r"Read the skill at\s+(\S+)")


@cache
def _tasks() -> list[dict]:
    return yaml.safe_load((ROOT / "eval.yaml").read_text())["tasks"]


def skill_path(instruction: str) -> str | None:
    """Return the path named on the `Read the skill at` line, or None."""
    match = SKILL_LINE.search(instruction)
    return match.group(1) if match else None


@pytest.mark.parametrize(
    ("instruction", "expected"),
    [
        ("Read the skill at skills/infrahub-common/SKILL.md and follow it.", "skills/infrahub-common/SKILL.md"),
        ("Read the skill at\n  skills/infrahub-common/SKILL.md\nthen", "skills/infrahub-common/SKILL.md"),
        ("Write a schema for a VLAN.", None),
        ("See skills/infrahub-common/SKILL.md for background.", None),
    ],
)
def test_skill_path_reads_only_the_skill_line(instruction: str, expected: str | None) -> None:
    assert skill_path(instruction) == expected


@pytest.mark.parametrize("task", _tasks(), ids=lambda t: t["name"])
def test_task_skill_path_exists(task: dict) -> None:
    path = skill_path(task.get("instruction", ""))
    assert path is not None, f"{task['name']}: no 'Read the skill at <path>' line"
    resolved = (ROOT / path).resolve()
    assert resolved.is_relative_to((ROOT / "skills").resolve()), (
        f"{task['name']}: {path} is outside the shipped skills/ tree"
    )
    assert resolved.is_file(), f"{task['name']}: {path} does not exist"


@cache
def _run_lines() -> list[str]:
    return [
        grader.get("run", "")
        for task in _tasks()
        for grader in task.get("graders", [])
    ]


@pytest.mark.parametrize(
    "script",
    sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob("graders/*/check_*.py")),
)
def test_task_grader_is_run_by_a_task(script: str) -> None:
    runs = _run_lines()
    assert runs, "eval.yaml has no grader run lines"
    assert any(script in shlex.split(run) for run in runs), (
        f"{script} is run by no eval.yaml task; wire it or delete it"
    )
