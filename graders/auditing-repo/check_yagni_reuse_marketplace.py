#!/usr/bin/env python3
"""Grader for yagni-reuse-existing-marketplace-schema.

Two-schema fixture: schemas/dcim.yml hand-rolls a marketplace-published
DCIM domain (must be flagged), while schemas/location.yml is pulled via
`infrahubctl marketplace get` and inherits from a marketplace generic —
the reuse pattern the rule wants, which must NOT be flagged (see the
rule's "What NOT to flag"). Presence/severity alone can't catch a
false positive on the compliant schema, so the attribution and
carve-out checks pin both sides.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "yagni-reuse-existing-marketplace-schema"
CHECKS = [
    f"yagni-finding-present:{RULE}",
    f"yagni-finding-severity:{RULE}:MEDIUM",
    f"yagni-finding-ladder-step:{RULE}:1",
    # Attribution: flag the hand-rolled DCIM schema, never the
    # marketplace-pulled + inherit_from location schema.
    f"yagni-finding-file:{RULE}:dcim",
    "yagni-finding-file-excludes:location",
    "yagni-no-above-medium",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
