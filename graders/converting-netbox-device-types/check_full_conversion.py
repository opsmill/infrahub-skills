#!/usr/bin/env python3
"""Grader for the netbox-convert-full-conversion eval task.

End-to-end assertion over a full conversion: envelope, template shape, naming, load order, and coverage reporting.

Usage::

    python check_full_conversion.py [output_dir]
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
    "no-model-data-on-template",
    "component-kind-wrapper",
    "component-names-namespaced",
    "device-type-object",
    "load-order-numbering",
    "coverage-report",
]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
