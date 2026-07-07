#!/usr/bin/env python3
"""Grader for the practices-transform-watch eval.

Asserts the auditor flags transforms whose undetectable dependencies lack a
``watch.files`` declaration, and — critically — that it never suggests
``watch`` on an ``artifact_definitions`` or ``generator_definitions`` entry
(those config models forbid the key; generator-side support is unreleased).

The shared ``lib.py`` finding checks key on a finding's ``rule`` and
``severity`` only, so they work for this ``practices-`` rule as-is. This rule
carries no ``ladder_step`` (it is not a YAGNI/cost-to-fix finding), so the
grader does not assert one, and it deliberately omits the ``yagni-*`` sort /
severity-cap checks, which iterate over yagni-prefixed findings only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "practices-transform-watch-dependencies"
CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"watch-not-on-artifact-generator:{RULE}",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
