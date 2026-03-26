#!/usr/bin/env python3
"""Grader script for infrahub-schema-creator location hierarchy eval.

Run from the eval output directory (where output.yml lives):

    python /path/to/check_location.py

Prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add the graders directory to sys.path so ``lib`` can be imported
# regardless of where this script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "hierarchical-generic",
    "inherit-from-generic",
    "root-no-parent",
    "human-friendly-id",
    "display-label-singular",
    "schema-version",
    "correct-hierarchy-chain",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
