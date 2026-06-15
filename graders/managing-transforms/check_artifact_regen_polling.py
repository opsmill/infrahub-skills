#!/usr/bin/env python3
"""Grader for the transform-artifact-regen-polling eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "posts-artifact-generate-endpoint",
    "has-polling-loop",
    "polls-coreartifact-after-post",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, {"py": Path("output.py")})))
