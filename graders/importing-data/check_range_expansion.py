#!/usr/bin/env python3
"""Grader for the csv-import-range-expansion eval task.

Asserts that when a child row name uses bracket-range syntax (e.g.,
``eth[0-47]``), the enclosing relationship block sets
``parameters.expand_range: true`` — otherwise the loader silently
creates one literal-named interface instead of expanding.

Usage::

    python check_range_expansion.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "range-expansion"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
