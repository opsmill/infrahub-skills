#!/usr/bin/env python3
"""Grader for the cascade-upstream eval task.

The upstream side of a cascade: creates one kind of object and exposes a
GeneratorTarget-derived schema so a downstream generator can guard with a
checksum. Universal-tier checks still apply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "allow-upsert-everywhere",
    "upstream-count-validation",
    "stable-iteration",
    "cascade-one-layer",
    "cascade-target-inheritance",
]

if __name__ == "__main__":
    result = run_checks(CHECKS, Path("."))
    print(json.dumps(result))
