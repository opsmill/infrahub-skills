#!/usr/bin/env python3
"""Grader script for the bug-sanitization eval task.

Checks that the rendered bug report does not leak IPs, internal
hostnames, tokens, or user filesystem paths, and that it has the
basic structural elements (title, environment section).

Usage::

    python check_bug_sanitization.py <output_file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECK_NAMES = [
    "has-title",
    "has-environment-section",
    "no-leaked-ips",
    "no-internal-hostnames",
    "no-tokens",
    "no-user-paths",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECK_NAMES, output_path)))


if __name__ == "__main__":
    main()
