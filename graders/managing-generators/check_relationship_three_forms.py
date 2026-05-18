#!/usr/bin/env python3
"""Grader for the generator-relationship-three-forms eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "hfid-form-for-name-lookup",
    "id-form-for-uuid",
    "sdk-object-reference-used",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.py"))))
