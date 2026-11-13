#!/usr/bin/env python3
"""Grader for the traces offer on a slowness that ended (rules/create-traces.md)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "mentions-create",
    # The slowness in this task has ended, so the window must be absolute.
    ("traces-offered-with-window", {"window": "absolute"}),
    "sampling-caveat",
    "review-before-sharing",
    # The review step names the traces (rules/review-before-sharing.md).
    "traces-review",
    "no-legacy-artifacts",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
