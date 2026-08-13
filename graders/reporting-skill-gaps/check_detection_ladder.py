#!/usr/bin/env python3
"""Grader for the evidence-detection-ladder eval (verifier-verdict path)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "cites-verifier-outcome",
    "cites-rule-file",
    "states-correction-delta",
    "has-proposed-change",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
