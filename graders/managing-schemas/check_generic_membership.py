#!/usr/bin/env python3
"""Grader for the generic-membership eval.

This task produces two files: the schema (`output.yml`) and the offline test
that pins the generic's implementer set (`output.py`). The load-bearing
assertions are that the new implementer is recorded as a decision about the
generic's consumers, and that the pin runs over the schema YAML rather than
against a live instance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "full-kind-references",
    "generic-membership-consumers-noted",
    "generic-implementer-set-pinned",
]


def _read(name: str) -> str:
    try:
        return Path(name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


if __name__ == "__main__":
    sources = {"py": _read("output.py")}
    print(json.dumps(run_checks(CHECKS, Path("output.yml"), sources=sources)))
