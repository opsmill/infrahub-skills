#!/usr/bin/env python3
"""Grader script for eval scenario: coexisting with Infrahub's built-in menu.

Checks assertion names:
    apiversion-and-kind, name-and-namespace, children-data-wrapper,
    no-builtin-section-recreated, parent-attaches-to-builtin

Usage::

    python check_builtin_sections.py <output_file>

Prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the graders package importable when executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks

CHECK_NAMES = [
    "apiversion-and-kind",
    "name-and-namespace",
    "children-data-wrapper",
    "no-builtin-section-recreated",
    "parent-attaches-to-builtin",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.yml")
    result = run_checks(CHECK_NAMES, output_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
