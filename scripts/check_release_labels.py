"""Validate the explicit release bump label selected for a pull request."""

# ruff: noqa: INP001

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import cast

BUMP_LABELS = frozenset({"changes/major", "changes/minor", "changes/patch"})
RELEASE_PR_PREFIX = "chore(release):"
RELEASE_PR_AUTHOR = "opsmill-bot"
# The branch auto-bump.yml pushes: `release/v` plus the version string it
# accepts, so no other branch name qualifies for the exemption. Both values are
# copied verbatim from that workflow, and a test fails if they drift.
RELEASE_BRANCH_PREFIX = "release/v"
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?"
RELEASE_BRANCH = re.compile(re.escape(RELEASE_BRANCH_PREFIX) + VERSION_PATTERN)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels-json", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--author-login", required=True)
    parser.add_argument("--head-repository", required=True)
    parser.add_argument("--repository", required=True)
    return parser


def fail(message: str) -> int:
    """Report a failure as a GitHub Actions error annotation."""
    sys.stdout.write(f"::error::{message}\n")
    return 1


def main() -> int:
    """Validate that a normal pull request has exactly one release label."""
    args = build_parser().parse_args()

    # A title prefix, not the exact generated title: editing the title re-runs
    # this check, and the bot author, same repository and release branch
    # already identify the pull request.
    if (
        args.author_login == RELEASE_PR_AUTHOR
        and args.head_repository == args.repository
        and RELEASE_BRANCH.fullmatch(args.head_ref)
        and args.title.startswith(RELEASE_PR_PREFIX)
    ):
        sys.stdout.write("Skipping label check for generated release pull request.\n")
        return 0

    try:
        raw_labels = json.loads(args.labels_json)
    except json.JSONDecodeError as exc:
        return fail(f"Invalid labels JSON: {exc}")

    if not isinstance(raw_labels, list) or not all(
        isinstance(label, str) for label in raw_labels
    ):
        return fail("Labels JSON must be an array of strings.")

    labels = cast("list[str]", raw_labels)
    selected = sorted(BUMP_LABELS.intersection(labels))
    if len(selected) != 1:
        choices = ", ".join(sorted(BUMP_LABELS))
        found = ", ".join(selected) if selected else "none"
        return fail(
            f"Pull requests must have exactly one release bump label ({choices}); found: {found}."
        )

    sys.stdout.write(f"Release bump label: {selected[0]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
