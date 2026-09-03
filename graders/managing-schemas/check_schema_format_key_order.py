#!/usr/bin/env python3
"""Grader for the schema-format-key-order eval task.

Asserts the emitted schema is authored in the canonical key order documented in
``skills/infrahub-managing-schemas/rules/format-schema-files.md`` — the order
``infrahubctl schema format`` writes, and the order to author by hand when the
installed ``infrahubctl`` predates that command. Bundled with the baseline
schema assertions so the task also catches regressions in the naming and
display rules.

Run from the eval output directory (where output.yml lives)::

    python /path/to/check_schema_format_key_order.py

Prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECK_NAMES = [
    # The rule under test
    "file-key-order",
    "entity-key-order",
    "order-weight-key-last",
    "choice-key-order",
    # Baseline regression cover
    "schema-version",
    "attr-min-length",
    "dropdown-for-status",
    "full-kind-references",
    "human-friendly-id",
    "display-label-singular",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.yml")
    print(json.dumps(run_checks(CHECK_NAMES, output_path)))


if __name__ == "__main__":
    main()
