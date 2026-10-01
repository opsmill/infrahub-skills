"""Validate the explicit release bump label selected for a pull request."""

# ruff: noqa: INP001

from __future__ import annotations

import argparse
import json
import sys
from typing import cast

BUMP_LABELS = frozenset({"changes/major", "changes/minor", "changes/patch"})
RELEASE_PR_PREFIX = "chore(release):"
RELEASE_PR_AUTHOR = "opsmill-bot"
# Dependabot security updates open unlabeled and the bot cannot add labels;
# its pull requests are dependency bumps by construction, as in
# changelog-check.yml. An exact login match: bot logins cannot be registered.
DEPENDABOT_AUTHOR = "dependabot[bot]"


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

    release_version = args.head_ref.removeprefix("release/")
    if (
        args.author_login == RELEASE_PR_AUTHOR
        and args.head_repository == args.repository
        and args.head_ref.startswith("release/v")
        and args.title == f"{RELEASE_PR_PREFIX} {release_version}"
    ):
        sys.stdout.write("Skipping label check for generated release pull request.\n")
        return 0

    if args.author_login == DEPENDABOT_AUTHOR:
        sys.stdout.write("Skipping label check for Dependabot pull request.\n")
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
