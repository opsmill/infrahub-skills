#!/usr/bin/env python3
"""Grader for the uniqueness-constraints eval task.

Verifies the preconditions the server enforces on any relationship a
uniqueness constraint reaches — ``optional: false`` and ``cardinality: one`` —
and the relationship path shape, which is inverted between the two fields:
``uniqueness_constraints`` takes the bare name, ``human_friendly_id`` takes a
peer-attribute path.

Does NOT verify the ``__value`` suffix on plain attribute entries; a bare
attribute name in a constraint is a separate server error
(``invalid attribute, it must end with one of the following properties: value``)
and is not asserted here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "uniqueness-rel-mandatory",
    "matching-identifiers",
    "full-kind-references",
    "human-friendly-id",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
