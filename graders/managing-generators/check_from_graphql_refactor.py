#!/usr/bin/env python3
"""Grader for the from-graphql-hydration-refactor eval task.

Reads ``output.md`` from CWD, extracts the ```python and ```graphql
fenced blocks, and asserts the generator was refactored to use
``InfrahubNode.from_graphql`` with matching query coverage.

Prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "python-block-present",
    "graphql-block-present",
    "imports-infrahub-node",
    "uses-from-graphql",
    "no-client-get-in-loop",
    "query-has-typename",
]


if __name__ == "__main__":
    output_path = Path("output.md")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
