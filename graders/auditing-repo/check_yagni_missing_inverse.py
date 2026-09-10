#!/usr/bin/env python3
"""Grader for the yagni-missing-inverse eval.

The standard rule/severity/ladder-step assertions, plus the one this rule
adds on top of them: the recommended inverse has to name a cardinality.
That value decides whether the inverse creates an inbound cap, so a finding
that leaves it unstated is not actionable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "yagni-missing-inverse-forces-python-filter"

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:3",
    f"yagni-finding-names-cardinality:{RULE}",
    "yagni-no-above-medium",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
