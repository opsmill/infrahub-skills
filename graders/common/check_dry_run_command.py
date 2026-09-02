#!/usr/bin/env python3
"""Grader for the common-dry-run-python-transform eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

# The transform name is the `common-dry-run-python-transform` fixture,
# passed as a check argument so the check is not pinned to this task.
CHECKS = [
    "python-transform-dry-run:spine_config",
    "cli-commands-exist",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
