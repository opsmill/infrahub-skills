#!/usr/bin/env python3
"""Grader for the building-sync-adapters-strict-fake eval: the test fake serves the captures and enforces the API behavior file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "fake-serves-captures",
    "fake-field-selection",
    "fake-drops-unknown",
    "fake-reference-shapes",
    "fake-next-link",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path())))
