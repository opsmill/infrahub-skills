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
from lib import check_value_drivers, run_checks  # noqa: E402

CHECK_NAMES = ["scope-split-f1-only", "features-artifacts", "plan-map-matches", "reference-design", "next-steps-in-order", "sketch-rows-complete", "value-drivers"]
# Neighbouring rules this task also grades: a failure lowers the score by its
# share instead of zeroing it. The pass threshold still decides the task.
NEIGHBOURS = ("sketch-rows-complete",)

# The figures a brief may cite to the request: those the task's prompt states
# ("the fabric of our two data centres"), and the counts of the lists it gives
# (three outage causes, three users of the data, four domains, four owning
# teams, two kinds of order). A test pins REQUEST_STATED to the prompt in
# eval.yaml. An estimate such as "40 hours" is in neither.
REQUEST_STATED = frozenset({"2"})
REQUEST_LIST_COUNTS = frozenset({"2", "3", "4"})
REQUEST_FIGURES = REQUEST_STATED | REQUEST_LIST_COUNTS


def grade(workspace: Path) -> dict:
    extra = {"value-drivers": lambda ws: check_value_drivers(ws, REQUEST_FIGURES)}
    return run_checks(CHECK_NAMES, workspace, extra, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
