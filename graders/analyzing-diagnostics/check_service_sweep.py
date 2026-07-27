#!/usr/bin/env python3
"""Grader for the non-server service-sweep findings-report eval."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "mentions-manifest",
    "cites-bundle-evidence",
    ("root-service", {"service": "message-queue"}),
    ("mentions-all", {"terms": "server,message-queue,task-worker"}),
    ("incident-grouping", {"max_incidents": 2}),
    "severity-labels",
    "no-mutating-commands",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
