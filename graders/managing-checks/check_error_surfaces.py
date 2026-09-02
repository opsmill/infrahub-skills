#!/usr/bin/env python3
"""Grader for the check-error-surfaces eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "uses-sdk-execute-graphql",
    "no-status-code-branch",
    "catches-graphql-error",
    "separate-local-bounds-branch",
]

if __name__ == "__main__":
    print(
        json.dumps(
            run_checks(CHECKS, Path("output.yml"), py_path=Path("output.py"))
        )
    )
