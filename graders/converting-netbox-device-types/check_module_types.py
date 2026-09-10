#!/usr/bin/env python3
"""Grader for the netbox-convert-module-types eval task.

NetBox module types are a second input family, told apart from device types
by carrying no `slug`. Against a schema whose module type has no component
relationships — the stock schema-library case — only the model identity and
the manufacturer link can land, and the component lists must be reported as
skipped rather than silently dropped.

Usage::

    python check_module_types.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "module-type-object", "coverage-report"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
