#!/usr/bin/env python3
"""Grader for the generator-relationship-hfid-encoding eval.

Reads ``output.py`` from the CWD and prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "relationship-hfid-form-correct",
    "no-bare-string-relationship",
    "no-overpacked-hfid-list",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.py"))))
