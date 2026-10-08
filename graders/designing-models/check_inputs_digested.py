#!/usr/bin/env python3
"""Grader for eval task: design-inputs-digested.

Every file the task provided is listed in the brief's Inputs and cited as
evidence for the sketch. INPUTS mirrors the files in the task's prompt, not
the skill's prose: it is the task's own fixture.
Usage: python check_inputs_digested.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_inputs_digested, run_checks  # noqa: E402

# File name -> CSV column headers (empty for files that are not tables).
INPUTS = {
    "pops.csv": ["pop_code", "name", "city", "region"],
    "backbone.txt": [],
}

CHECK_NAMES = ["inputs-digested", "sketch-rows-complete", "decision-provenance"]


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    extra = {"inputs-digested": lambda ws: check_inputs_digested(ws, INPUTS)}
    print(json.dumps(run_checks(CHECK_NAMES, workspace, extra)))


if __name__ == "__main__":
    main()
