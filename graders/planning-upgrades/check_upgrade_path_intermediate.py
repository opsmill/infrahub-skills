#!/usr/bin/env python3
"""Grader for the upgrade-path-intermediate-releases eval.

Scores whether the plan read every hop's release notes rather than only the
target's. 1.6.0 and 1.8.0 both carry breaking changes between 1.5.2 and
1.10.0, and neither is flagged in docs frontmatter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import PLAN_FILE, run_checks  # noqa: E402

CHECKS = [
    ("every-hop-enumerated", {"releases": "1.6.0,1.8.0"}),
    ("sequential-hops", {"source": "1.5", "target": "1.10"}),
    "verdict-has-evidence",
    "finding-vocabulary",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(PLAN_FILE)
    print(json.dumps(run_checks(CHECKS, out)))
