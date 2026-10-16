#!/usr/bin/env python3
"""Grader for the service-cascade eval task.

Verifies that the HealthCheck relationship resolves to on_delete: cascade,
that every IP reference resolves to no-action, and that the surrounding
schema follows other baseline rules.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "on-delete-cascade-present",
    "ip-reference-not-cascade",
    "parent-rel-optional-false",
    "matching-identifiers",
    "full-kind-references",
    "human-friendly-id",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
