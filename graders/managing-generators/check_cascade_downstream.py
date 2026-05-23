#!/usr/bin/env python3
"""Grader for the cascade-downstream eval task.

The downstream side of a cascade: creates one kind of object, guards saves
with a checksum derived from inputs (and prefixed by GENERATOR_VERSION).
All three universal-tier checks apply — partial-data safety
(upstream-count-validation) is just as important downstream as upstream.
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
    "kind-literal",
    "no-broad-except",
    "no-early-return",
    "no-self-read-after-create",
    "filters-parallel",
    "upstream-update-group-context",
    "cascade-one-layer",
    "cascade-checksum-guard",
    "cascade-version-constant",
]

if __name__ == "__main__":
    result = run_checks(CHECKS, Path("."))
    print(json.dumps(result))
