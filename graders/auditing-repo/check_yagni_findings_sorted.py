#!/usr/bin/env python3
"""Grader: assert all 11 yagni-* findings emit sorted by ladder_step ascending.

Companion to the per-rule graders. The fixture for this task contains
violations of all 11 yagni-* rules; the auditor must emit them in
ascending ladder_step order (cheapest fix on top).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

ALL_RULES = [
    # (rule, ladder_step, severity) — severity tracks the ladder, capped at
    # MEDIUM: cheap, unambiguous fixes (steps 1-3) emit MEDIUM; costlier
    # rewrites where the Python is more defensible (steps 4-6) emit LOW.
    ("yagni-reuse-existing-marketplace-schema", 1, "MEDIUM"),
    ("yagni-duplicate-shape-not-extracted-to-generic", 2, "MEDIUM"),
    ("yagni-generator-hardcoding-data", 2, "MEDIUM"),
    ("yagni-custom-domain-primitives-instead-of-builtin", 2, "MEDIUM"),
    ("yagni-imperative-allocation-vs-resource-pool", 2, "MEDIUM"),
    ("yagni-python-validator-vs-schema-constraint", 3, "MEDIUM"),
    ("yagni-missing-inverse-forces-python-filter", 3, "MEDIUM"),
    ("yagni-denormalized-vs-indirect-relationship", 4, "LOW"),
    ("yagni-generator-query-shape-too-broad", 4, "LOW"),
    ("yagni-python-transform-that-could-be-jinja2", 5, "LOW"),
    ("yagni-redundant-check-that-graphql-can-answer", 6, "LOW"),
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
