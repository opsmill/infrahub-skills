#!/usr/bin/env python3
"""Grader for eval task: design-docs-lookup.

The task's design needs the cage generator to run the moment a cage is
created. No local skill rule covers what starts a Generator on a node change,
so the brief has to rest that decision on a documentation page found through
llms.txt. SUBJECT matches the rows about that trigger; it is the task's own
fixture.
Usage: python check_documented_decision.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_documented_decision, run_checks  # noqa: E402

SUBJECT = re.compile(
    r"\bautomatic|\btrigger|\bevent\b|as soon as|the moment|\b(?:is|are|gets?) (?:created|added)\b|\bon creat",
    re.IGNORECASE,
)

CHECK_NAMES = ["documented-decision", "mechanisms-match-artifacts", "sketch-rows-complete"]
# Neighbouring rules this task also grades: a failure lowers the score by its
# share instead of zeroing it. The pass threshold still decides the task.
NEIGHBOURS = ("mechanisms-match-artifacts", "sketch-rows-complete")


def grade(workspace: Path) -> dict:
    extra = {"documented-decision": lambda ws: check_documented_decision(ws, SUBJECT, "the cage generator")}
    return run_checks(CHECK_NAMES, workspace, extra, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
