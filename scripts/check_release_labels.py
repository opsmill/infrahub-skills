"""Validate the explicit release bump label selected for a pull request."""

# ruff: noqa: INP001

from __future__ import annotations

import argparse
import json
import sys
from typing import cast

BUMP_LABELS = frozenset({"changes/major", "changes/minor", "changes/patch"})
RELEASE_PR_PREFIX = "chore(release):"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels-json", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--head-ref", required=True)
    return parser


def main() -> int:
    """Validate that a normal pull request has exactly one release label."""
    args = build_parser().parse_args()

    if args.title.startswith(RELEASE_PR_PREFIX) and args.head_ref.startswith(
        "release/"
    ):
        sys.stdout.write("Skipping label check for generated release pull request.\n")
        return 0

    try:
        raw_labels = json.loads(args.labels_json)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Invalid labels JSON: {exc}\n")
        return 1

    if not isinstance(raw_labels, list) or not all(
        isinstance(label, str) for label in raw_labels
    ):
        sys.stderr.write("Labels JSON must be an array of strings.\n")
        return 1

    labels = cast("list[str]", raw_labels)
    selected = sorted(BUMP_LABELS.intersection(labels))
    if len(selected) != 1:
        choices = ", ".join(sorted(BUMP_LABELS))
        found = ", ".join(selected) if selected else "none"
        sys.stderr.write(
            f"Pull requests must have exactly one release bump label ({choices}); found: {found}.\n"
        )
        return 1

    sys.stdout.write(f"Release bump label: {selected[0]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
