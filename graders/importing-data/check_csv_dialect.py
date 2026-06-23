#!/usr/bin/env python3
"""Grader for the csv-import-csv-dialect eval task.

Asserts dialect detection produces clean values — no BOM bytes left in
emitted strings, no semicolon-soup from misread delimiters.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "csv-dialect"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
