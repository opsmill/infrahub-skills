#!/usr/bin/env python3
"""Grader for the netbox-convert-fallback-sources eval task.

Combines the generic fallback checks from ``lib`` with assertions specific
to this task's fixture. Precedence — *which* competing source should win for
a given record — is only decidable against a known input, so it is asserted
here rather than in the shared library: from output alone, "comments won
because description was absent" is indistinguishable from "comments won
although description was set", and the first is correct behaviour.

The fixture is the Catalyst 9200L-24T in ``eval.yaml``. If that prompt
changes, update these expectations with it.

Usage::

    python check_fallback_sources.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import (  # noqa: E402
    _object_docs,
    _rows,
    _template_rows,
    component_children,
    load_output_dir,
    run_checks,
)

CHECKS = ["envelope", "template-kind", "fallback-precedence", "coverage-report"]

#: The device type description must come from NetBox `description`.
EXPECTED_DEVICE_DESCRIPTION = "Fixed-uplink access switch for branch sites"

#: Interface name to the description it must end up with, given the fixture.
#: 1/0/1 has both (primary wins), 1/0/2 has only a label (fallback fills in),
#: 1/0/3 has only a description, 1/0/4 has neither.
EXPECTED_INTERFACES = {
    "GigabitEthernet1/0/1": "Primary uplink to the distribution layer",
    "GigabitEthernet1/0/2": "Uplink B",
    "GigabitEthernet1/0/3": "Spare access port",
    "GigabitEthernet1/0/4": None,
}


def check_fixture_precedence(output_dir: Path) -> tuple[bool, str]:
    """Assert the fixture's competing fields resolved the declared way."""
    parsed = load_output_dir(output_dir)

    device_types = [
        row
        for doc in _object_docs(parsed)
        if "devicetype" in str(doc["spec"].get("kind", "")).lower()
        for row in _rows(doc)
    ]
    if not device_types:
        return False, "No device type rows found"
    actual = str(device_types[0].get("description", ""))
    if actual != EXPECTED_DEVICE_DESCRIPTION:
        return False, (
            f"Device type description is {actual!r}; expected the NetBox "
            f"description {EXPECTED_DEVICE_DESCRIPTION!r}, not the comments URL"
        )

    children = {
        child.get("name"): child
        for row in _template_rows(parsed)
        for _, child in component_children(row)
    }
    for name, expected in EXPECTED_INTERFACES.items():
        if name not in children:
            return False, f"Interface {name!r} was not emitted"
        got = children[name].get("description")
        if expected is None and got is not None:
            return False, f"Interface {name!r} has description {got!r}; expected none"
        if expected is not None and got != expected:
            return False, f"Interface {name!r} has description {got!r}; expected {expected!r}"
    return True, "Fixture precedence and fallback resolution are correct"


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    result = run_checks(CHECKS, output_dir)

    ok, message = check_fixture_precedence(output_dir)
    result["checks"].append({"name": "fixture-precedence", "passed": ok, "message": message})

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
