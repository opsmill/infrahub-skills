#!/usr/bin/env python3
"""Grader for the common-dry-run-generator eval.

Covers the two constraints deployment-gql-dry-run.md and
managing-generators/rules/testing-integration.md add about running a
generator locally: the target is a `key=value` query variable, not a bare
id, and the run names a branch because it writes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "generator-target-is-key-value",
    "cli-commands-exist",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
