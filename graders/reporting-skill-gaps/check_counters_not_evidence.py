#!/usr/bin/env python3
"""Grader for the counters-only path of evidence-detection-ladder.

Session-shape counters (retries, edit churn, repeated asks) open an
investigation and never close one. With nothing else to go on, the correct
output withholds the draft and names the probe that came up empty.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "no-draft-without-detection-evidence",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
