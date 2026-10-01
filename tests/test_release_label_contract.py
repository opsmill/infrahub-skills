"""Regression tests for the release bump label contract."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess  # noqa: S404
import sys

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / ".github" / "version-drafter.yml"
LABELS_PATH = ROOT / ".github" / "labels.yml"
CHECKER_PATH = ROOT / "scripts" / "check_release_labels.py"

CANONICAL_CONFIG = """---
# Only explicit release-intent labels drive semantic version bumps.
major-labels:
  - "changes/major"
minor-labels:
  - "changes/minor"
patch-labels:
  - "changes/patch"
"""


def run_checker(
    labels: list[str],
    *,
    title: str = "fix: example",
    head_ref: str = "feature/example",
) -> subprocess.CompletedProcess[str]:
    """Run the label checker as the workflow does."""
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(CHECKER_PATH),
            "--labels-json",
            json.dumps(labels),
            "--title",
            title,
            "--head-ref",
            head_ref,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_release_label_contract() -> None:
    assert CONFIG_PATH.read_text() == CANONICAL_CONFIG

    declared_labels = LABELS_PATH.read_text()
    for label in ("changes/major", "changes/minor", "changes/patch"):
        assert f'name: "{label}"' in declared_labels

        accepted = run_checker([label, "type/housekeeping"])
        assert accepted.returncode == 0, accepted.stderr
        assert label in accepted.stdout

    for labels in ([], ["type/bug"], ["changes/patch", "changes/minor"]):
        rejected = run_checker(labels)
        assert rejected.returncode != 0
        assert "exactly one" in rejected.stderr

    spoofed_release_pr = run_checker([], title="chore(release): ordinary pull request")
    assert spoofed_release_pr.returncode != 0
    assert "exactly one" in spoofed_release_pr.stderr

    release_pr = run_checker(
        [],
        title="chore(release): v1.2.3",
        head_ref="release/v1.2.3",
    )
    assert release_pr.returncode == 0, release_pr.stderr
    assert "generated release pull request" in release_pr.stdout
