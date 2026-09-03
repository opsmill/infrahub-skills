#!/usr/bin/env python3
"""Grader for the relationship-traversal-check eval task.

This task grades the produced GraphQL query and Python check (not an
`.infrahub.yml`), so it reads `output.gql` / `output.py` and delegates to
`run_text_checks` in lib.py — the text-based counterpart to `run_checks`.

The load-bearing assertions are on the query: a check runs one query with no
lazy fetch, so the related node's comparison attribute must be pulled inside
the query, in the innermost related node's own selection set. The Python
assertions confirm the violation is surfaced and, critically, that an
unresolvable related node is flagged rather than skipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_text_checks  # noqa: E402

CHECKS = [
    "child-status-filter",
    "traverses-related-node",
    "fetches-related-attribute-value",
    "uses-infrahubcheck",
    "surfaces-violation",
    "null-safe-traversal",
    "flags-unresolvable-parent",
]


def _read(name: str) -> str:
    try:
        return Path(name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


if __name__ == "__main__":
    sources = {"gql": _read("output.gql"), "py": _read("output.py")}
    print(json.dumps(run_text_checks(CHECKS, sources)))
