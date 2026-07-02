#!/usr/bin/env python3
"""Parameterized grader for a single yagni-* rule.

Usage:
    check_yagni_rule.py <rule-name> <severity> <ladder-step>

Asserts the audit emitted exactly the expected finding for one rule —
present, at the expected severity and ladder_step — plus the class-wide
MEDIUM severity cap. Multi-artifact tasks that also need file-attribution
or carve-out checks (generator-hardcoding, imperative-allocation, the
full sorted set) keep their own bespoke grader scripts.

Collapses what used to be nine near-identical 23-line scripts differing
only in three constants into one script invoked with args from eval.yaml.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(json.dumps({
            "score": 0.0,
            "details": "usage: check_yagni_rule.py <rule> <severity> <step>",
            "checks": [],
        }))
        sys.exit(0)
    rule, severity, step = sys.argv[1], sys.argv[2], sys.argv[3]
    checks = [
        f"yagni-finding-present:{rule}",
        f"yagni-finding-severity:{rule}:{severity}",
        f"yagni-finding-ladder-step:{rule}:{step}",
        "yagni-no-above-medium",
    ]
    print(json.dumps(run_checks(checks, Path("output.json"))))
