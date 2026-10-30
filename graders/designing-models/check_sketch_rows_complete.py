#!/usr/bin/env python3
"""Grader for eval task: design-sketch-rows-complete.

Unknown owners become open items instead of invented values. The task's
transcript leaves the SSID owner unknown; SUBJECT names that row and column,
which is the task's own fixture, not the skill's prose.
Usage: python check_sketch_rows_complete.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_open_item_for, run_checks  # noqa: E402

SSID = re.compile(r"ssid", re.IGNORECASE)

CHECK_NAMES = ["sketch-rows-complete", "unknown-owner-open", "model-map-matches", "open-items-name-features", "decision-provenance"]
# Neighbouring rules this task also grades; a failure costs only its share.
NEIGHBOURS = ("decision-provenance",)


def grade(workspace: Path) -> dict:
    extra = {"unknown-owner-open": lambda ws: check_open_item_for(ws, SSID, "owner")}
    return run_checks(CHECK_NAMES, workspace, extra, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
