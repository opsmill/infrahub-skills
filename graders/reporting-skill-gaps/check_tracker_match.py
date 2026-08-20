#!/usr/bin/env python3
"""Grader for the tracker-first eval, match branch.

An issue already covers the friction, so the correct output drafts a
comment carrying the new evidence rather than a second issue. See
rules/workflow-tracker-first.md.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "searches-tracker-first",
    "comments-not-duplicates",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
