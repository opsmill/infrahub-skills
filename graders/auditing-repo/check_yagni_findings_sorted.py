#!/usr/bin/env python3
"""Grader: assert all 9 yagni-* findings emit sorted by ladder_step ascending.

Companion to the per-rule graders. The fixture for this task contains
violations of all 9 yagni-* rules; the auditor must emit them in
ascending ladder_step order (cheapest fix on top).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

ALL_RULES = [
    # (rule, ladder_step, severity) — all yagni rules cap at MEDIUM by policy
    ("yagni-duplicate-shape-not-extracted-to-generic", 2, "MEDIUM"),
    ("yagni-generator-hardcoding-data", 2, "MEDIUM"),
    ("yagni-custom-domain-primitives-instead-of-builtin", 2, "MEDIUM"),
    ("yagni-python-validator-vs-schema-constraint", 3, "MEDIUM"),
    ("yagni-missing-inverse-forces-python-filter", 3, "MEDIUM"),
    ("yagni-denormalized-vs-indirect-relationship", 4, "MEDIUM"),
    ("yagni-generator-query-shape-too-broad", 4, "MEDIUM"),
    ("yagni-python-transform-that-could-be-jinja2", 5, "MEDIUM"),
    ("yagni-redundant-check-that-graphql-can-answer", 6, "MEDIUM"),
]

CHECKS: list[str] = []
for rule, step, sev in ALL_RULES:
    CHECKS.append(f"yagni-finding-present:{rule}")
    CHECKS.append(f"yagni-finding-severity:{rule}:{sev}")
    CHECKS.append(f"yagni-finding-ladder-step:{rule}:{step}")
CHECKS.append("yagni-findings-sorted")
CHECKS.append("yagni-no-above-medium")

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
