#!/usr/bin/env python3
"""Grader for the artifact-svg-content-type eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "artifact-content-type-declared",
    "svg-transform-returns-str",
    "no-yaml-dict-confusion",
]

if __name__ == "__main__":
    print(
        json.dumps(
            run_checks(
                CHECKS,
                {"py": Path("output.py"), "md": Path("output.md")},
            )
        )
    )
