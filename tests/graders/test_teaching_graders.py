"""Subprocess smoke tests: every teaching-concepts task grader runs and
emits well-formed skillgrade JSON on both a compliant and an empty
workspace."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRADER_DIR = REPO_ROOT / "graders" / "teaching-concepts"

SCRIPTS = [
    "check_probe_first.py",
    "check_structured_lesson.py",
    "check_record_progress.py",
    "check_sandbox_branch.py",
    "check_verified_solution.py",
    "check_learner_authors.py",
    "check_hint_ladder.py",
    "check_own_artifacts.py",
    "check_cite_docs.py",
    "check_graduation.py",
    "check_off_map.py",
    "check_competitor.py",
]


def run_grader(script: str, workspace: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(GRADER_DIR / script), str(workspace)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("script", SCRIPTS)
def test_empty_workspace_scores_zero(tmp_path, script):
    result = run_grader(script, tmp_path)
    assert result["score"] == 0.0
    assert result["checks"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_output_shape(tmp_path, script):
    result = run_grader(script, tmp_path)
    assert set(result) == {"score", "details", "checks"}
    for check in result["checks"]:
        assert set(check) == {"name", "passed", "message"}
