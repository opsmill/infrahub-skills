#!/usr/bin/env python3
"""Grader for the netbox-convert-load-order eval task.

Asserts the three object files are numbered in dependency order and the device type carries the model data.

Usage::

    python check_load_order.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "load-order-numbering", "device-type-object"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
