#!/usr/bin/env python3
"""Grader for the csv-import-column-to-attribute eval task.

Asserts that the column-to-attribute mapping ladder produced clean bindings:

- Every emitted attribute name is in the fixture's allowed attribute set for
  its kind (no invented attributes, no schema mutation by stealth).
- No emitted attribute name carries raw CSV header artifacts (spaces,
  parentheses, slashes) — the snake_case round-trip must have run.
- No "memory_tb" / "memory_kb"-style unit-mismatch bindings: when the
  schema only declares a units-bearing attribute (``memory_gb``), the
  emission must use that exact name; converted-unit columns route to the
  interview, not a silent rename.

Usage::

    python check_column_to_attribute.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "column-to-attribute"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
