#!/usr/bin/env python3
"""Grader for the netbox-convert-bundled-scripts eval task.

Asserts the output carries the guarantees only the bundled converter makes:
integer numerics, unwrapped choice values, and a coverage report. A
hand-rolled conversion of the task's input fails at least one.

Usage::

    python check_bundled_scripts.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "envelope",
    "template-kind",
    "bundled-script-output",
    "component-kind-wrapper",
    "coverage-report",
]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
