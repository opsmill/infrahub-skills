#!/usr/bin/env python3
"""Grader script for the redaction compliance eval task.

Verifies that a diagnostics bundle has redaction artifacts in place
and that no unredacted secrets leaked into any file:

- Bundle root files (``manifest.yml``, ``README.md``)
- No unredacted secrets anywhere in the bundle
- ``redaction-report.txt`` is present and non-empty

Usage::

    python check_redaction_compliance.py <bundle-path>

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
    "no-unredacted-secrets",
    "redaction-report-present",
]


def main() -> None:
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_bundle")
    result = run_checks(CHECKS, bundle)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
