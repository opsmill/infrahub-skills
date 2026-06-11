#!/usr/bin/env python3
"""Grader script for the flag-emission eval task.

Verifies the bundle correctly emits an ``oom-in-logs`` flag when
an ``OutOfMemoryError`` line is present in a worker log:

- Bundle root files (``manifest.yml``, ``README.md``)
- ``flags.yml`` is a YAML list with valid entries
- ``oom-in-logs`` flag is present in ``flags.yml``

Usage::

    python check_flag_emission.py <bundle-path>

Prints skillgrade JSON to stdout. Pass criterion is ``score == 1.0``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "bundle-root",
    "flags-yml-shape",
    ("flag-fired", {"flag_id": "oom-in-logs"}),
]


def main() -> None:
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_bundle")
    result = run_checks(CHECKS, bundle)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
