#!/usr/bin/env python3
"""Grader for the schema-generate-profile eval task.

Verifies generate_profile lives on the concrete node (never the generic)
and the baseline schema hygiene checks still pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "generate-profile-concrete-only",
    "human-friendly-id",
    "no-deprecated-string",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.yml"))))
