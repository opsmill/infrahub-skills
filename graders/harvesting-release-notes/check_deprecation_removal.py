#!/usr/bin/env python3
"""Grader for the harvest-release-notes-deprecation-removal eval.

The workspace holds release notes for infrahub-v1.6.0 to infrahub-v1.7.0
(plus a 1.7.0b1 pre-release), source snapshots per tag, and a skill that
teaches the `name__like` filter with no version gate. 1.6.0 deprecates the
filter and 1.7.0 removes it, so a correct report recommends a gate naming
both releases, leaves no release without working guidance (`name__like` up to
at least 1.6, `name__contains` from 1.6), pins its evidence,
rates the finding High (the old guidance now fails with an error), and leaves
the skill files untouched. Every affected passage must exist, so the 1.7.0
removal of INFRAHUB_LEGACY_CACHE, which no skill mentions, cannot be a finding.

The hashes pin the workspace skill files as shipped; the test in
tests/graders/test_harvesting_release_notes_lib.py fails if they drift from
the fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import REPORT_FILE, run_checks  # noqa: E402

AFFECTED = "skills/acme-querying-inventory/rules/filters.md"

SKILL_FILES = {
    "skills/acme-querying-inventory/SKILL.md": "d26fb2189e2f11b1534a6997329c794b92007108fcfe0982df4addea0a874324",
    "skills/acme-querying-inventory/rules/filters.md": "c392af00c6ff2cc1e4b03a06ba51adb961b20eea36919171bb66592ab0e3be2e",
}

CHECKS = [
    "report-has-findings",
    "finding-fields-present",
    "affected-paths-exist",
    ("target-finding-present", {"affected_path": AFFECTED}),
    ("evidence-pinned", {"start": "1.6.0", "end": "1.7.0"}),
    ("gate-boundaries", {"affected_path": AFFECTED, "deprecated": "1.6", "removed": "1.7"}),
    (
        "gate-keeps-old-guidance",
        {
            "affected_path": AFFECTED,
            "old_token": "name__like",
            "new_token": "name__contains",
            "removed": "1.7",
            "deprecated": "1.6",
        },
    ),
    ("severity", {"affected_path": AFFECTED, "expected": "high"}),
    ("skill-unchanged", {"files": SKILL_FILES}),
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(REPORT_FILE)
    print(json.dumps(run_checks(CHECKS, out)))
