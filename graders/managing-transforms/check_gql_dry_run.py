#!/usr/bin/env python3
"""Grader for the transform-query-dry-run-before-merge eval.

Backs the shared rule
``skills/infrahub-common/rules/deployment-gql-dry-run.md``: a query
change must be dry-run against a live schema before merge, because
``infrahubctl schema check`` and YAML validation do not catch
GraphQL/schema mismatches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "dry-run-executes-query",
    "dry-run-before-merge",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, {"md": Path("output.md")})))
