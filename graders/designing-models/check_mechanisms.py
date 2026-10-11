#!/usr/bin/env python3
"""Grader for eval task: design-mechanisms.

The brief's Mechanisms table matches the artifacts each feature lists, and
the uniqueness rule the prompt asks for is a schema constraint, not a check.
UNIQUENESS mirrors that rule in the task's prompt; it is the task's fixture.
Usage: python check_mechanisms.py [workspace_dir]
Prints skillgrade JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import check_uniqueness_is_schema_constraint, run_checks  # noqa: E402

UNIQUENESS = re.compile(r"vlan.*(uniq|duplicat|same|twice|clash|shar)|(uniq|duplicat|same|twice|clash|shar).*vlan", re.IGNORECASE)

CHECK_NAMES = ["mechanisms-match-artifacts", "uniqueness-is-a-schema-constraint", "sketch-rows-complete"]


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    extra = {"uniqueness-is-a-schema-constraint": lambda ws: check_uniqueness_is_schema_constraint(ws, UNIQUENESS)}
    print(json.dumps(run_checks(CHECK_NAMES, workspace, extra)))


if __name__ == "__main__":
    main()
