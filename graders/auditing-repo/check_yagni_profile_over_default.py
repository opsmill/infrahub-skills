#!/usr/bin/env python3
"""Grader for yagni-profile-over-default."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "yagni-profile-over-default"
CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:2",
    "yagni-no-above-medium",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
