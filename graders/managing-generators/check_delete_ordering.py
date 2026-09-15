#!/usr/bin/env python3
"""Grader for the generator-delete-ordering eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["detach-before-peer-delete"]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.py"))))
