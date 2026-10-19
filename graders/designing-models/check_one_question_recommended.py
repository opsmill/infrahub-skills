#!/usr/bin/env python3
"""Grader for eval task: design-one-question-recommended.

The next interview message is one question block with one recommended option.
Usage: python check_one_question_recommended.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECK_NAMES = ["one-question-recommended"]


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(run_checks(CHECK_NAMES, workspace)))


if __name__ == "__main__":
    main()
