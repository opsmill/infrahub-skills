#!/usr/bin/env python3
"""Grader for the string-length-limits eval task.

Asserts that no `description`, `label`, `identifier`, or `deprecation`
field on any node/generic/attribute/relationship exceeds Infrahub's
schema-load max_length cap. Caps are fetched at run time from the
public Infrahub JSON Schema at
``https://schema.infrahub.app/infrahub/schema/latest.json`` so the
grader stays correct across Infrahub versions without needing a
running server. Bundled with baseline schema-shape checks so this
task also guards against regressions in unrelated rules under the
same prompt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "string-limits",
    "human-friendly-id",
    "full-kind-references",
    "no-deprecated-string",
]

if __name__ == "__main__":
    output_path = Path("output.yml")
    result = run_checks(CHECKS, output_path)
    print(json.dumps(result))
