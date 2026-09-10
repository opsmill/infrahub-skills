#!/usr/bin/env python3
"""Grader for the yagni-duplicate-shape-paired-rel eval.

The sibling nodes share six attributes, so the duplicate-shape finding must
still fire. What the shared parameterized grader cannot express is the rule's
carve-out: each sibling's `device` relationship points at a different peer, and
hoisting it onto the generic would freeze that peer and erase the pairing. The
finding has to say so and leave the relationship on the concrete kinds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "yagni-duplicate-shape-not-extracted-to-generic"

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:2",
    f"yagni-finding-discloses:{RULE}:paired-relationship-stays-put",
    "yagni-no-above-medium",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
