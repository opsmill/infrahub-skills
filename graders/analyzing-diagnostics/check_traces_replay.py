#!/usr/bin/env python3
"""Grader for opening the traces of a bundle in a local Tempo (rules/triage-traces.md)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS: list[str | tuple[str, dict]] = [
    "mentions-manifest",
    # The customer's Tempo in the task's manifest; the traces must not go there.
    ("traces-replayed-by-id", {"customer_host": "tempo.monitoring.acme.internal"}),
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
