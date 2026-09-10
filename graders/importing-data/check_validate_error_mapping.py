#!/usr/bin/env python3
"""Grader for the csv-import-validate-error-mapping eval task.

Asserts the server error is mapped back to the CSV cell, with the emitted YAML marked off-limits.

Usage::

    python check_validate_error_mapping.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ['error-traced-to-source-row']


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
