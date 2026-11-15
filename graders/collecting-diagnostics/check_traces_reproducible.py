#!/usr/bin/env python3
"""Grader for the traces offer and the sampling ratio advice for a reproducible slowness (rules/create-traces.md)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "mentions-create",
    "traces-offered-with-window",
    "ratio-raise-and-remove",
    "ratio-address-set",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
