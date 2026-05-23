#!/usr/bin/env python3
"""Grader for the generator-basic eval task.

Runs all three universal-tier checks: allow-upsert, upstream count validation,
and stable iteration. The basic task is a vanilla single-generator prompt that
should naturally satisfy every universal rule.
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
