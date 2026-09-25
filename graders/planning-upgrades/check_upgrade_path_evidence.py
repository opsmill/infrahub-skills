#!/usr/bin/env python3
"""Grader for the upgrade-path-evidence eval.

Scores whether each finding carries a verdict backed by something locatable,
rather than a generic warning restated in the Evidence column.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import PLAN_FILE, run_checks  # noqa: E402

CHECKS = [
    "verdict-has-evidence",
    "finding-vocabulary",
    ("sequential-hops", {"source": "1.9", "target": "1.10"}),
    "no-mutating-commands",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(PLAN_FILE)
    print(json.dumps(run_checks(CHECKS, out)))
