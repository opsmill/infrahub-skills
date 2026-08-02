#!/usr/bin/env python3
"""Grader for the netbox-convert-shared-relationship eval task.

Two NetBox component lists can land on a single Infrahub relationship when
their peer kinds share a generic — a console-port node that inherits the
interface generic rides the device's `interfaces` relationship. The output
must keep both, as a list of `{kind, data}` blocks the object loader
resolves per item.

Fixture-specific counts live here rather than in the shared library,
because "did anything get erased" is only decidable against a known input.
The fixture is the Catalyst 9300-24P in `eval.yaml`; update these together.

Usage::

    python check_shared_relationship.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import _template_rows, component_blocks, load_output_dir, run_checks  # noqa: E402

CHECKS = [
    "envelope",
    "template-kind",
    "component-kind-wrapper",
    "component-names-namespaced",
    "shared-relationship-blocks",
]

#: Physical interfaces and console ports declared by the eval fixture.
EXPECTED_PHYSICAL = 4
EXPECTED_CONSOLE = 2


def check_fixture_counts(output_dir: Path) -> tuple[bool, str]:
    """Assert neither component list was erased by the other."""
    rows = _template_rows(load_output_dir(output_dir))
    if not rows:
        return False, "No Template* rows found"

    counts: dict[str, int] = {}
    for row in rows:
        for _, block in component_blocks(row):
            kind = str(block.get("kind"))
            counts[kind] = counts.get(kind, 0) + len(block.get("data") or [])

    physical = sum(count for kind, count in counts.items() if "Physical" in kind)
    console = sum(count for kind, count in counts.items() if "Console" in kind)

    if physical != EXPECTED_PHYSICAL or console != EXPECTED_CONSOLE:
        return False, (
            f"Expected {EXPECTED_PHYSICAL} physical interface templates and "
            f"{EXPECTED_CONSOLE} console templates; got {physical} and {console} "
            f"(kinds seen: {counts}). One list likely overwrote the other."
        )
    return True, (f"Both lists survived: {physical} physical interfaces, {console} console ports")


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    result = run_checks(CHECKS, output_dir)

    ok, message = check_fixture_counts(output_dir)
    result["checks"].append({"name": "fixture-counts", "passed": ok, "message": message})

    passed = sum(1 for entry in result["checks"] if entry["passed"])
    total = len(result["checks"])
    result["score"] = round(passed / total, 4) if total else 0.0
    failed = [entry["name"] for entry in result["checks"] if not entry["passed"]]
    result["details"] = (
        f"{passed}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
