#!/usr/bin/env python3
"""Grader for the csv-import-fail-closed eval task.

Asserts the skill fails closed on an unmapped column: no Object-envelope
document in the output directory carries any ``spec.data`` rows (i.e. no
partial write that silently drops the column).

Only the ``fail-closed`` check runs here. The usual ``envelope`` baseline is
intentionally omitted — a correct fail-closed run emits no object YAML, so an
envelope check would contradict the very behavior under test.

Usage::

    python check_fail_closed.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["fail-closed"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
