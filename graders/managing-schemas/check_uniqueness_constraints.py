#!/usr/bin/env python3
"""Grader for the uniqueness-constraints eval task.

Verifies the constraint format (``__value`` on attributes, bare names on
relationships) and the preconditions the server enforces on any relationship a
constraint reaches: ``optional: false`` and ``cardinality: one``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "uniqueness-rel-mandatory",
    "matching-identifiers",
    "full-kind-references",
    "human-friendly-id",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
