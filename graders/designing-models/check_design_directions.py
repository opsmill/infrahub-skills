#!/usr/bin/env python3
"""Grader for eval task: design-directions.

The next interview message offers two or three design directions, each with
its decisions by ID, so the user can pick one or combine them.
Usage: python check_design_directions.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECK_NAMES = ["one-question-recommended", "design-directions"]
# Neighbouring rules this task also grades; a failure costs only its share.
NEIGHBOURS = ("one-question-recommended",)


def grade(workspace: Path) -> dict:
    return run_checks(CHECK_NAMES, workspace, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
