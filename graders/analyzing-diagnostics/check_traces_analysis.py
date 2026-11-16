#!/usr/bin/env python3
"""Grader for reading the trace files of a bundle (rules/triage-traces.md)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS: list[str | tuple[str, dict]] = [
    "mentions-manifest",
    # The slow span of trace 0001 in the task: a Git sync task whose children
    # take about 21 ms of its 10.74 s.
    (
        "traces-slow-span",
        {
            "span": "Sync Git Repositories",
            "service": "infrahub-task-worker",
            "duration": r"10[.,]7\d*\s*(s|sec|seconds)\b|107\d\d(\.\d+)?\s*ms\b",
        },
    ),
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
