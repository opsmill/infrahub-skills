#!/usr/bin/env python3
"""Grader for the generator-empty-input-guard eval task.

Reads ``output.py`` from CWD and asserts that, when the collection it loops
over is empty, the generator re-claims the previous run's members before it
returns, alongside the idempotent-write baseline. A raise also keeps the
previous output, but it fails the run, and the task says the run must not
fail on an empty list.

Prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "empty-input-reclaims",
    "preflight-or-upsert",
    "no-raw-create-without-handler",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.py"))))
