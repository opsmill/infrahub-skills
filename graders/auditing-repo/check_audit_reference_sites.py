#!/usr/bin/env python3
"""Grader for the audit-reference-sites eval.

The fixture repo references the denormalized `site_name` attribute in four
places. The fourth, `templates/device_interfaces.j2`, is reachable only by
walking a double-quoted `{% import "..." %}` out of the registered template,
and `templates/device.j2` is an unregistered lookalike that is not a render
site at all. A finding proposing to remove the attribute has to name the four
and only the four.

Severity and the class-level cap ride along so this task also catches a
regression in the underlying yagni rule's grading.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

RULE = "yagni-denormalized-vs-indirect-relationship"
SITES = (
    "schemas/dcim.yml,templates/device_config.j2,"
    "templates/device_interfaces.j2,queries/device_info.gql"
)

CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"audit-sites-complete:{RULE}:{SITES}",
    f"yagni-finding-severity:{RULE}:LOW",
    f"yagni-finding-ladder-step:{RULE}:4",
    "yagni-no-above-medium",
]

# The site list is the finding. An answer that emits a well-formed finding
# citing one file has done none of the work the rule asks for, and ungated it
# banks 4/5, comfortably over the threshold.
GATE_CHECKS = (f"audit-sites-complete:{RULE}:{SITES}",)

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"), GATE_CHECKS)))
