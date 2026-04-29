#!/usr/bin/env python3
"""Grader for the parent-relationships eval task.

Verifies that any relationship with kind: Parent is non-optional, has
cardinality: one, and is unique per node — the three constraints enforced
server-side by `_validate_parents_one_schema`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "parent-rel-optional-false",
    "parent-rel-single",
    "matching-identifiers",
    "full-kind-references",
    "human-friendly-id",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
