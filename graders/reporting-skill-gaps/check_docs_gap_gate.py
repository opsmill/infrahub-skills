#!/usr/bin/env python3
"""Grader for the docs-gap settled-behavior gate eval.

A `bug(docs):` issue asks an Infrahub maintainer to write down an answer,
so it is only actionable once an answer exists. When the underlying
behavior is still being designed, or is deliberately left undocumented,
the correct move is to explain which behavior is unsettled and stop,
rather than file a request nobody can fulfill.

This is the only place the workflow stops without producing a report. It
is not a confidence question: `marks-confidence` answers those with a
label rather than with silence. `no-docs-gap-when-unsettled` already
requires both the withheld draft and the stated reason, so it stands
alone here.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "no-docs-gap-when-unsettled",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECKS, out)))
