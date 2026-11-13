#!/usr/bin/env python3
"""Grader for the building-sync-adapters-identifiers-hfid eval: sync identifiers match the destination human-friendly ID."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "identifiers-match-hfid",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path())))
