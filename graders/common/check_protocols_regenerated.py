#!/usr/bin/env python3
"""Grader for the common-protocols-regenerate-from-server eval.

Covers the constraint that the committed protocol file is regenerated from
a running server, never written by `infrahubctl protocols --schemas`,
bundled with the invented-command baseline so the task also catches a
regression there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "protocols-regenerated-from-server:lib/protocols.py",
    "cli-commands-exist",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
