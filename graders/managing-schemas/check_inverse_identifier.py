#!/usr/bin/env python3
"""Grader for the inverse-identifier-reuse eval task.

Verifies that when the model adds a missing inverse relationship, it reuses
the forward side's pre-existing (auto-generated-looking) identifier verbatim
rather than inventing a new one and renaming the forward side — the latter
fails with `not_supported` on a live instance because the identifier is
immutable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "inverse-reuses-forward-identifier",
    "matching-identifiers",
    "full-kind-references",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
