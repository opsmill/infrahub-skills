#!/usr/bin/env python3
"""Grader script for eval scenario: removing items from a git-synced menu.

Checks assertion names:
    apiversion-and-kind, name-and-namespace, children-data-wrapper,
    removed-items-dropped, removed-items-deleted

Usage::

    python check_remove_synced_items.py [<output_file> [<notes_file>]]

Prints skillgrade JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the graders package importable when executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks

CHECK_NAMES = [
    "apiversion-and-kind",
    "name-and-namespace",
    "children-data-wrapper",
    "removed-items-dropped",
    "removed-items-deleted",
]

# The synced menu file the task prompt shows, split by what the user asked for.
# The next sync deletes these, so the answer should leave them to it.
REMOVED_IDS = frozenset(
    {
        ("Campus", "FloorMenu"),
        ("Campus", "WirelessMenu"),
        ("Campus", "AccessPointMenu"),
        ("Campus", "ControllerMenu"),
    }
)
KEPT_IDS = frozenset(
    {
        ("Campus", "SitesMenu"),
        ("Campus", "BuildingMenu"),
        ("Campus", "SwitchingMenu"),
        ("Campus", "SwitchMenu"),
    }
)
# Loaded by hand with infrahubctl menu load and never in the repository, so
# the sync never tracked it: only a delete removes it.
HAND_LOADED_IDS = frozenset({("Campus", "LabMenu")})


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.yml")
    notes_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("notes.md")
    result = run_checks(
        CHECK_NAMES,
        output_path,
        apply_path=notes_path,
        removed_ids=REMOVED_IDS,
        kept_ids=KEPT_IDS,
        hand_delete_ids=HAND_LOADED_IDS,
        sync_removed_ids=REMOVED_IDS,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
