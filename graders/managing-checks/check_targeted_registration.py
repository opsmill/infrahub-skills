#!/usr/bin/env python3
"""Grader for the targeted-check-registration eval task.

Same baseline as global-check-registration plus the targeted-specific
requirement that `targets` and `parameters` are declared (and `query:`
is still rejected — this is the most common confusion vs.
generator_definitions which DOES require a top-level query field).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "check-definitions-present",
    "no-query-field-in-check-def",
    "only-allowed-fields-in-check-def",
    "queries-section-present",
    "check-def-required-fields",
    "targeted-has-targets-and-parameters",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
