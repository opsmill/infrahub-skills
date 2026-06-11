#!/usr/bin/env python3
"""Grader for the network-diagram-file-object eval task.

Verifies that CoreFileObject is inherited by a concrete node (not a generic),
that the five reserved file-metadata attributes are not redeclared, and that
the bypass antipattern (Text attribute storing a path/URL) is not used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "core-file-object-inherited",
    "file-object-on-node-not-generic",
    "no-reserved-file-attrs",
    "no-filename-text-bypass",
    "human-friendly-id",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
