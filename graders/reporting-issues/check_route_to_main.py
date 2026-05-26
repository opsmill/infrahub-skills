#!/usr/bin/env python3
"""Grader for the route-to-main-on-doubt eval task.

Asserts that the routing decision names `opsmill/infrahub` as the target
and cites user uncertainty as the reason.

Usage::

    python check_route_to_main.py <output_file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECK_NAMES = [
    "routes-to-main",
    "cites-uncertainty",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECK_NAMES, output_path)))


if __name__ == "__main__":
    main()
