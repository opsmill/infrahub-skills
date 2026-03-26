#!/usr/bin/env python3
"""Grader script for eval scenario: flat menu.

Checks assertion names:
    apiversion-and-kind, spec-data-structure, name-and-namespace,
    kind-for-schema-links, mdi-icons, labels-present

Usage::

    python check_flat_menu.py <output_file>

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
    "spec-data-structure",
    "name-and-namespace",
    "kind-for-schema-links",
    "mdi-icons",
    "labels-present",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("menu.yml")
    result = run_checks(CHECK_NAMES, output_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
