#!/usr/bin/env python3
"""Grader for the csv-import-hfid-reference-shape eval task.

Asserts that relationship references match target HFID arity — single-element
HFID targets get a scalar reference, multi-element HFID targets get a list
of the correct length.

Usage::

    python check_hfid_reference_shape.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "hfid-reference-shape"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
