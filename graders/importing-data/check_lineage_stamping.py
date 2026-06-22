#!/usr/bin/env python3
"""Grader for the csv-import-lineage-stamping eval task.

Asserts that opt-in lineage stamping uses the value+metadata mapping form
on every imported value, with the expected ``source:`` tag:

- Every attribute on every emitted row is a mapping with ``value:`` and
  ``source:`` keys (not a plain scalar).
- ``source:`` matches the expected import tag from the fixture.

Usage::

    python check_lineage_stamping.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "lineage-stamping"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
