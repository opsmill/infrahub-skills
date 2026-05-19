#!/usr/bin/env python3
"""Grader for the computed-jinja2-name eval task.

Verifies that a Jinja2-derived attribute is paired with read_only: true and
uses the correct computed_attribute.kind shape.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "computed-jinja2-readonly",
    "computed-jinja2-kind",
    "no-deprecated-string",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
