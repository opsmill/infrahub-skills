#!/usr/bin/env python3
"""Grader for the audit-proposed-syntax eval.

The fixture pins a version whose attribute filter generator emits only the
singular value, the plural values, an isnull boolean, node-property ids and
flag booleans. No numeric range filter exists. An audit that proposes `__gte`
to push the count to the server recommends a call that fails at runtime, and
the finding reads exactly like a verified one.

Both halves are graded. The finding must say how it established its syntax,
and the syntax must not be the one that does not exist. The first check
without the second passes "same form as the sibling query".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

RULE = "yagni-redundant-check-that-graphql-can-answer"

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"audit-verified-against:{RULE}",
    f"audit-replacement-omits:{RULE}:__gte",
    f"audit-replacement-omits:{RULE}:__lte",
    "yagni-no-above-medium",
]

# Recommending a filter the audited version does not implement is the defect,
# not a fifth of it.
GATE_CHECKS = (
    f"audit-replacement-omits:{RULE}:__gte",
    f"audit-replacement-omits:{RULE}:__lte",
)

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"), GATE_CHECKS)))
