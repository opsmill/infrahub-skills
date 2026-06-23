#!/usr/bin/env python3
"""Grader for the csv-import-component-children-shape eval task.

Asserts that component children are emitted as ``<rel>: {kind, data: [...]}``
mappings, not as bare lists of dicts (which is the common antipattern when
the relationship peer is a generic).

Usage::

    python check_component_children_shape.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "component-children-shape"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
