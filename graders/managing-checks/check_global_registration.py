#!/usr/bin/env python3
"""Grader for the global-check-registration eval task.

Verifies the model produced an `.infrahub.yml` with a properly shaped
check_definitions entry that does NOT contain the rejected `query:`
field, and registers the backing GraphQL query under the top-level
`queries:` section.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "check-definitions-present",
    "no-query-field-in-check-def",
    "only-allowed-fields-in-check-def",
    "queries-section-present",
    "check-def-required-fields",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
