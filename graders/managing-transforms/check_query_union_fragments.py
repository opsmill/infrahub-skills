#!/usr/bin/env python3
"""Grader for the transform-query-union-fragments eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "query-uses-inline-fragments-for-location",
    "query-no-direct-field-on-union-location",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, {"gql": Path("output.gql")})))
