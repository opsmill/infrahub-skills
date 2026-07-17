#!/usr/bin/env python3
"""Grader for the object-profiles-and-templates eval task.

Verifies the object YAML assigns a profiles list, creates an object from an
object_template, sets at least one explicit override on a profile-assigned
object, and authors a template object under a Template<Kind> kind.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "object-assigns-profiles",
    "object-uses-object-template",
    "object-overrides-profile-value",
    "object-authors-template",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.yml"))))
