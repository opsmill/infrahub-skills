#!/usr/bin/env python3
"""Grader for eval task: design-decision-provenance.

Every decision says whether the user stated it or accepted a recommendation.
SUBJECTS mirrors the transcript in the task's prompt (three answers stated,
two recommendations accepted); it is the task's own fixture.
Usage: python check_decision_provenance.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_decision_tags_for, run_checks  # noqa: E402


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


SUBJECTS = {
    "circuit identity": (_p(r"circuit id"), "stated"),
    "providers": (_p(r"provider"), "stated"),
    "bandwidth": (_p(r"bandwidth"), "stated"),
    "the endpoint generic": (_p(r"generic"), "recommended"),
    "contract end dates": (_p(r"end[ _-]?date"), "recommended"),
}

CHECK_NAMES = ["decision-provenance", "decision-tags-match", "sketch-rows-complete"]


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    extra = {"decision-tags-match": lambda ws: check_decision_tags_for(ws, SUBJECTS)}
    print(json.dumps(run_checks(CHECK_NAMES, workspace, extra)))


if __name__ == "__main__":
    main()
