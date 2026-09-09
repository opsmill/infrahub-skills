#!/usr/bin/env python3
"""Grader for eval task: teach-learner-authors.

Checks assertion names: learner-authors, verified-solution.
Usage: python check_learner_authors.py <workspace_dir>
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECK_NAMES = ["learner-authors", "verified-solution"]


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(run_checks(CHECK_NAMES, workspace)))


if __name__ == "__main__":
    main()
