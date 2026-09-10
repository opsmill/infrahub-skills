#!/usr/bin/env python3
"""Grader for practices-watch-dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

RULE = "practices-watch-dependencies"
CHECKS = [
    # The Python transform importing a sibling and the shared package, with
    # no watch key at all — the highest-cost case.
    f"watch-flags-entry:{RULE}:transforms/device_config.py",
    # The generator whose watch list names the shared package but omits the
    # sibling query model beside it: a list that reads complete but is not.
    f"watch-flags-entry:{RULE}:generators/generate_fabric.py",
    # Negative controls. Both are already correct; flagging either is noise.
    f"watch-does-not-flag-entry:{RULE}:transforms/interface_names.py",
    f"watch-does-not-flag-entry:{RULE}:templates/startup_config_arista.j2",
    # The fix must never land on a section whose model forbids the key, and
    # must never name an installed package.
    "watch-not-on-forbidden-section",
    f"watch-no-third-party-in-fix:{RULE}",
    # Advisory, not a failure: severity stays within the MEDIUM band.
    f"yagni-finding-severity:{RULE}:MEDIUM",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.json"))))
