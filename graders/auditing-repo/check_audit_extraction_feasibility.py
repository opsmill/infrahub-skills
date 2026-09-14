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

# This fixture trips two blockers at once: the three kinds declare the parent
# edge under three identifiers, and CircuitEndpoint peers LocationBuilding
# where the other two peer LocationSite. The rule states the two as equal
# blockers and gives no precedence, so either verdict is a correct read and
# pinning one fails an audit that named the other.
BLOCKED = "blocked-differing-identifiers|blocked-differing-peers"

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"audit-extraction-feasibility:{RULE}:{BLOCKED}",
    f"audit-sites-complete:{RULE}:{SITES}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:2",
    "yagni-no-above-medium",
]

# `clear` on an extraction that would collapse three identifiers into one is
# the finding that has to fail. Ungated it scores 5/6 and banks the task.
GATE_CHECKS = (
    f"audit-extraction-feasibility:{RULE}:{BLOCKED}",
)

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"), GATE_CHECKS)))
