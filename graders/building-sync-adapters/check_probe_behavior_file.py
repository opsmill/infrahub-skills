#!/usr/bin/env python3
"""Grader for the building-sync-adapters-probe-behavior-file eval: the API behavior file records what the captures show."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "behavior-keys",
    "behavior-covers-endpoints",
    "behavior-next-link",
    "behavior-rate-limit",
    "behavior-field-quirks",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path())))
