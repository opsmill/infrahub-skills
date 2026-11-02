#!/usr/bin/env python3
"""Grader for the csv-import-no-schema-mutation eval task.

Asserts that the skill fails closed on unmapped columns: no Object document
carries rows, no YAML file in the emitted output directory is a schema
document (``version: 1.0`` + ``nodes:`` / ``generics:``), and no file lives
under a ``schemas/`` sub-path of the output dir.

``envelope`` is not bundled here. It fails an empty output dir, and an
empty output dir is the correct answer for this input.

Usage::

    python check_no_schema_mutation.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["fail-closed", "no-schema-mutation"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
