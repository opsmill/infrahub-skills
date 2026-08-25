#!/usr/bin/env python3
"""Grader for the transform-watch-dependencies eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "watch-present-on-python-transforms",
    "watch-uses-object-form",
    "watch-declares-sibling-import",
    "watch-declares-outside-package-import",
    "watch-empty-for-self-contained",
    "watch-omitted-for-static-jinja2",
    "watch-declares-dynamic-jinja2-partials",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, {"yml": Path("output.yml")})))
