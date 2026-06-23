#!/usr/bin/env python3
"""Grader for the csv-import-single-kind-envelope eval task.

Asserts that every emitted YAML document under the output directory carries
a well-formed Object envelope (apiVersion, kind: Object, spec.kind,
spec.data list).

Usage::

    python check_envelope.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
