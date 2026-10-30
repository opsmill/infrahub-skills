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

# A Behavior about VLANs that states the rule itself ("No two branches share a
# VLAN", "VLAN uniqueness", "Reject a VLAN ID another branch already uses"),
# not a build-out row that mentions a unique VLAN or shared pools.
UNIQUENESS = re.compile(
    r"""^(?=.*vlan).*?(?:
        \bno\s+two\b | \btwo\b.*\b(?:shar|same|us) | \bsame\s+vlan
        | \bnever\b.*\b(?:shar|reus|twice|duplicat|clash)
        | \b(?:prevent|stop|reject|block|forbid) | duplicat | \btwice\b | \bclash
        | \balready\s+(?:us|in\s+use) | vlan.{0,20}\bunique\b | uniqueness
    )""",
    re.IGNORECASE | re.VERBOSE,
)

CHECK_NAMES = ["mechanisms-match-artifacts", "uniqueness-is-a-schema-constraint", "sketch-rows-complete"]
# Neighbouring rules this task also grades; a failure costs only its share.
NEIGHBOURS = ("sketch-rows-complete",)


def grade(workspace: Path) -> dict:
    extra = {"uniqueness-is-a-schema-constraint": lambda ws: check_uniqueness_is_schema_constraint(ws, UNIQUENESS)}
    return run_checks(CHECK_NAMES, workspace, extra, neighbours=NEIGHBOURS)


def main() -> None:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(grade(workspace)))


if __name__ == "__main__":
    main()
