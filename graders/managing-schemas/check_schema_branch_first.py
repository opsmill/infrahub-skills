#!/usr/bin/env python3
"""Grader for the schema-branch-first eval task.

Asserts that the schema rollout plan scopes the change to a dedicated branch
(not the default branch) and explains why — either by cautioning against
loading straight to the default branch or by routing the change through the
proposed-change / merge review path. The plan is free-form Markdown, so the
checks inspect the raw text.

Usage::

    python check_schema_branch_first.py <output_file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECK_NAMES = [
    "recommends-branch",
    "explains-default-branch-risk-or-review",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECK_NAMES, output_path)))


if __name__ == "__main__":
    main()
