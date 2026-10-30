#!/usr/bin/env python3
"""Grader for eval task: design-scope-split.

A too-big scope is split into ordered features and only F1 is sketched.
Usage: python check_scope_split.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECK_NAMES = ["scope-split-f1-only", "features-artifacts", "plan-map-matches", "reference-design", "next-steps-in-order", "sketch-rows-complete", "value-drivers"]
# Neighbouring rules this task also grades; a failure costs only its share.
NEIGHBOURS = ("sketch-rows-complete",)


def grade(workspace: Path) -> dict:
    return run_checks(CHECK_NAMES, workspace, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
