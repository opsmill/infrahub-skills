#!/usr/bin/env python3
"""Grader for eval task: design-inputs-digested.

Every file the task provided is listed in the brief's Inputs, and each sketch
row cites the file its facts came from, with a locator. INPUTS and SOURCES
mirror the files in the task's prompt, not the skill's prose: they are the
task's own fixture.
Usage: python check_inputs_digested.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_inputs_digested, run_checks  # noqa: E402

# File name -> CSV column headers (empty for files that are not tables).
INPUTS = {
    "pops.csv": ["pop_code", "name", "city", "region"],
    "backbone.txt": [],
}

# File name -> the node kinds whose facts the task's prompt puts in that file.
# The words come from the task's prompt; they are the task's fixture.
SOURCES = {
    # Checked in this order; a row is bound to the first file whose pattern
    # its node kind matches, so a SiteLink is a backbone.txt fact.
    "backbone.txt": re.compile(
        r"router|device|core|\bpe\b|link|connection|span|path|circuit|trunk|adjacency|backbone",
        re.IGNORECASE,
    ),
    "pops.csv": re.compile(r"pop|region|location|site", re.IGNORECASE),
}

CHECK_NAMES = ["inputs-digested", "sketch-rows-complete", "decision-provenance"]


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    extra = {"inputs-digested": lambda ws: check_inputs_digested(ws, INPUTS, SOURCES)}
    print(json.dumps(run_checks(CHECK_NAMES, workspace, extra)))


if __name__ == "__main__":
    main()
