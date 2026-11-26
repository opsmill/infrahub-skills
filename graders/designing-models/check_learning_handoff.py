#!/usr/bin/env python3
"""Grader for eval task: design-learning-handoff.

The user asked what a generator and a proposed change are, so Next steps send
them to the tutor for those two concepts, before the first feature's step.
CONCEPTS mirrors the questions in the task's prompt, spelled as the tutor's
concept map spells them; a test pins both to the map.
Usage: python check_learning_handoff.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_learning_step, run_checks  # noqa: E402

CONCEPTS = frozenset({"generators", "proposed-changes"})

CHECK_NAMES = ["learning-step", "next-steps-in-order", "sketch-rows-complete"]
# Neighbouring rules this task also grades: a failure lowers the score by its
# share instead of zeroing it. The pass threshold still decides the task.
NEIGHBOURS = ("sketch-rows-complete",)


def grade(workspace: Path) -> dict:
    extra = {"learning-step": lambda ws: check_learning_step(ws, CONCEPTS)}
    return run_checks(CHECK_NAMES, workspace, extra, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
