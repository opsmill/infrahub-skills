#!/usr/bin/env python3
"""Grader for the yagni-python-validator-uniqueness-scope eval.

Two artifacts, opposite verdicts. The task hands the auditor one check
that must be flagged and one that must not:

- ``checks/check_switch_name_unique.py`` guards a single concrete kind
  over a mandatory relationship. It is flaggable, and the replacement has
  to name that concrete kind — naming the shared generic instead widens
  the rule to every implementer, which is a different change.
- ``checks/check_pdu_rack_unique.py`` guards an *optional* relationship.
  The schema rejects an optional relationship in a uniqueness constraint
  at load, so there is no cheaper layer to move to and the finding does
  not apply.

The parameterized ``check_yagni_rule.py`` covers presence, severity and
ladder_step only, so neither carve-out is expressible there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "yagni-python-validator-vs-schema-constraint"

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:3",
    f"yagni-finding-file:{RULE}:check_switch_name_unique",
    f"yagni-replacement-mentions:{RULE}:DcimSwitch",
    f"yagni-replacement-excludes:{RULE}:DcimGenericDevice",
    "yagni-finding-file-excludes:check_pdu_rack_unique",
    "yagni-no-above-medium",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
