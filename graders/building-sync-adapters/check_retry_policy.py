#!/usr/bin/env python3
"""Grader for the building-sync-adapters-retry-policy eval: the client implements the default retry policy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "retry-status-set",
    "retry-after-honored",
    "retry-after-cap",
    "backoff-capped-jitter",
    "no-tls-retry",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path())))
