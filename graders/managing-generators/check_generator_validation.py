#!/usr/bin/env python3
"""Grader for the generator-validation eval task.

The prompt for this task emphasizes safety under partial upstream data. All
three universal checks run, but the failure of upstream-count-validation is
the rule this task is designed to expose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "allow-upsert-everywhere",
    "upstream-count-validation",
    "stable-iteration",
    "kind-literal",
    "no-broad-except",
    "no-early-return",
    "no-self-read-after-create",
    "filters-parallel",
    "upstream-update-group-context",
]

if __name__ == "__main__":
    result = run_checks(CHECKS, Path("."))
    print(json.dumps(result))
