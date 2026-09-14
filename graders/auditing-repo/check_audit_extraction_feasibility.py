#!/usr/bin/env python3
"""Grader for the audit-extraction-feasibility eval.

Three kinds share a parent relationship and a dropdown. The relationship
cannot be hoisted: the three edges carry three different identifiers, and
identifiers are immutable once loaded. The dropdown can be, but only once the
third kind's narrower choice list is accounted for, because hoisting the wider list
silently widens what that kind accepts.

So the finding must report a blocked verdict rather than `clear`, and must
name all three declaring kinds rather than the two that mirror each other.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

RULE = "yagni-duplicate-shape-not-extracted-to-generic"
SITES = "schemas/dcim.yml,schemas/circuit.yml,schemas/rack.yml"

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"audit-extraction-feasibility:{RULE}:blocked-differing-identifiers",
    f"audit-sites-complete:{RULE}:{SITES}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    "yagni-no-above-medium",
]

# `clear` on an extraction that would collapse three identifiers into one is
# the finding that has to fail. Ungated it scores 4/5 and banks the task.
GATE_CHECKS = (
    f"audit-extraction-feasibility:{RULE}:blocked-differing-identifiers",
)

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"), GATE_CHECKS)))
