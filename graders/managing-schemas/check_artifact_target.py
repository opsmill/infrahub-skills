#!/usr/bin/env python3
"""Grader for the device-artifact-target eval task.

Verifies that CoreArtifactTarget is inherited only by concrete nodes (not
generics) and that generate_template, when used, lives on a concrete node.
The two flags must remain independently set, not bundled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "core-artifact-target-concrete",
    "generate-template-concrete-only",
    "human-friendly-id",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
