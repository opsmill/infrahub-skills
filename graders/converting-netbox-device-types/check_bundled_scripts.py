#!/usr/bin/env python3
"""Grader for the netbox-convert-bundled-scripts eval task.

Asserts the output carries the guarantees only the bundled converter makes:
integer numerics, unwrapped choice values, and a coverage report. A
hand-rolled conversion of the task's input fails at least one.

Usage::

    python check_bundled_scripts.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import _every_row, run_checks  # noqa: E402

CHECKS = [
    "envelope",
    "template-kind",
    "bundled-script-output",
    "component-kind-wrapper",
    "coverage-report",
]

#: The task's input carries ``weight: 7.59`` with ``weight_unit: kg``. The
#: bundled converter rounds that to a whole number of the schema's unit; 8 is
#: the only correct answer for this fixture.
EXPECTED_WEIGHT = 8


def check_weight_is_the_rounded_value(
    parsed: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """The weight survived conversion, as the rounded whole number.

    The registry's ``bundled-script-output`` check can only reject a float,
    because it has no idea what any given input weighed. That left the
    cheapest wrong answer scoring full marks: drop ``weight`` altogether and
    there is no float to find. A hand-roll that cannot make 7.59 loadable is
    likeliest to do exactly that.
    """
    weights = [
        (label, row["weight"]) for label, row in _every_row(parsed) if "weight" in row
    ]
    if not weights:
        return False, (
            "No row carries a weight. The input weighs 7.59 kg, so dropping the "
            "field is a lost attribute, not a conversion."
        )
    wrong = [(label, value) for label, value in weights if value != EXPECTED_WEIGHT]
    if wrong:
        return False, (
            f"Expected weight {EXPECTED_WEIGHT} from 7.59 kg rounded; found "
            + ", ".join(f"{value!r} on {label}" for label, value in wrong)
        )
    return True, f"Weight converted to {EXPECTED_WEIGHT}, rounded from 7.59 kg"


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    extra = [("weight-rounds-to-a-whole-number", check_weight_is_the_rounded_value)]
    print(json.dumps(run_checks(CHECKS, output_dir, extra=extra)))


if __name__ == "__main__":
    main()
