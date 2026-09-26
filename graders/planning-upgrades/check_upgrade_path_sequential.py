#!/usr/bin/env python3
"""Grader for the upgrade-path-sequential eval.

Scores the N-1 rule: a 1.6.3 -> 1.9.0 request must produce three sequential
minor hops that chain end to end, not one consolidated jump.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import PLAN_FILE, run_checks  # noqa: E402

CHECKS = [
    ("sequential-hops", {"source": "1.6", "target": "1.9"}),
    "verdict-has-evidence",
    "finding-vocabulary",
    "no-mutating-commands",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(PLAN_FILE)
    print(json.dumps(run_checks(CHECKS, out)))
