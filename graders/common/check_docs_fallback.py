#!/usr/bin/env python3
"""Grader for the docs-fallback-delete-node eval task.

Asserts that a task not covered by the loaded skill is answered by
consulting the official docs (cited) and flagged as outside the skill's
tested rules, rather than silently answered from training.

Usage::

    python check_docs_fallback.py <output_file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECK_NAMES = ["docs-fallback"]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECK_NAMES, output_path)))


if __name__ == "__main__":
    main()
