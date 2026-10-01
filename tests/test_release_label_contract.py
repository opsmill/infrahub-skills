"""Regression tests for the release bump label contract."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess  # noqa: S404
import sys

import yaml

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / ".github" / "version-drafter.yml"
LABELS_PATH = ROOT / ".github" / "labels.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
CHECKER_PATH = ROOT / "scripts" / "check_release_labels.py"
REPOSITORY = "opsmill/infrahub-skills"

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
    author_login: str = "contributor",
    head_repository: str = "contributor/example",
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
            "--author-login",
            author_login,
            "--head-repository",
            head_repository,
            "--repository",
            REPOSITORY,
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
        assert accepted.returncode == 0, accepted.stdout
        assert label in accepted.stdout

    for labels in ([], ["type/bug"], ["changes/patch", "changes/minor"]):
        rejected = run_checker(labels)
        assert rejected.returncode != 0
        assert "::error::" in rejected.stdout
        assert "exactly one" in rejected.stdout

    spoofed_release_pr = run_checker(
        [],
        title="chore(release): v1.2.3",
        head_ref="release/v1.2.3",
    )
    assert spoofed_release_pr.returncode != 0
    assert "exactly one" in spoofed_release_pr.stdout

    forked_bot_release_pr = run_checker(
        [],
        title="chore(release): v1.2.3",
        head_ref="release/v1.2.3",
        author_login="opsmill-bot",
    )
    assert forked_bot_release_pr.returncode != 0
    assert "exactly one" in forked_bot_release_pr.stdout

    edited_title_release_pr = run_checker(
        [],
        title="chore(release): v1.2.3 (smoke rerun)",
        head_ref="release/v1.2.3",
        author_login="opsmill-bot",
        head_repository=REPOSITORY,
    )
    assert edited_title_release_pr.returncode == 0, edited_title_release_pr.stdout

    mismatched_title_release_pr = run_checker(
        [],
        title="fix: v1.2.3",
        head_ref="release/v1.2.3",
        author_login="opsmill-bot",
        head_repository=REPOSITORY,
    )
    assert mismatched_title_release_pr.returncode != 0
    assert "exactly one" in mismatched_title_release_pr.stdout

    non_release_branch_pr = run_checker(
        [],
        title="chore(release): v1.2.3",
        head_ref="feature/v1.2.3",
        author_login="opsmill-bot",
        head_repository=REPOSITORY,
    )
    assert non_release_branch_pr.returncode != 0
    assert "exactly one" in non_release_branch_pr.stdout

    release_pr = run_checker(
        [],
        title="chore(release): v1.2.3",
        head_ref="release/v1.2.3",
        author_login="opsmill-bot",
        head_repository=REPOSITORY,
    )
    assert release_pr.returncode == 0, release_pr.stdout
    assert "generated release pull request" in release_pr.stdout

    for head_ref in ("release/vnext", "release/v1.2.3/extra", "release/v1.2"):
        loose_branch_release_pr = run_checker(
            [],
            title="chore(release): v1.2.3",
            head_ref=head_ref,
            author_login="opsmill-bot",
            head_repository=REPOSITORY,
        )
        assert loose_branch_release_pr.returncode != 0, head_ref
        assert "exactly one" in loose_branch_release_pr.stdout

    prerelease_pr = run_checker(
        [],
        title="chore(release): v1.2.3-rc.1",
        head_ref="release/v1.2.3-rc.1",
        author_login="opsmill-bot",
        head_repository=REPOSITORY,
    )
    assert prerelease_pr.returncode == 0, prerelease_pr.stdout

    unlabeled_dependabot_pr = run_checker(
        [],
        title="chore(deps): bump example",
        head_ref="dependabot/uv/example-1.2.3",
        author_login="dependabot[bot]",
        head_repository=REPOSITORY,
    )
    assert unlabeled_dependabot_pr.returncode != 0
    assert "exactly one" in unlabeled_dependabot_pr.stdout


def test_dependabot_pull_requests_carry_a_bump_label() -> None:
    declared_labels = LABELS_PATH.read_text()
    updates = yaml.safe_load(DEPENDABOT_PATH.read_text())["updates"]
    assert updates
    for update in updates:
        labels = update.get("labels", [])
        bump_labels = [label for label in labels if label.startswith("changes/")]
        assert bump_labels == ["changes/patch"], update["package-ecosystem"]
        for label in labels:
            assert f'name: "{label}"' in declared_labels, label
