#!/usr/bin/env python3
"""Grader for yagni-imperative-allocation-vs-resource-pool.

Asserts the audit flags imperative resource allocation (subnet math /
random selection / hand-rolled free-scan loop) as a finding pointing at
the built-in resource-pool layer, at MEDIUM / ladder_step 2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "yagni-imperative-allocation-vs-resource-pool"
CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:2",
    # File attribution: the finding must point at the production generator
    # (provision_circuit.py), and the deterministic-derivation generator
    # (router_id.py) must NOT be flagged — see the rule's "What NOT to flag".
    f"yagni-finding-file:{RULE}:provision_circuit",
    "yagni-finding-file-excludes:router_id",
    "yagni-no-above-medium",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
