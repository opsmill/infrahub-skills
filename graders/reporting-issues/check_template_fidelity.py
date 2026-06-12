#!/usr/bin/env python3
"""Grader for the template-fidelity eval task.

Asserts that the plan references fetching the repo's bug_report.yml
template via `gh api` and names opsmill/infrahub as the target.

Usage::

    python check_template_fidelity.py <output_file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECK_NAMES = [
    "uses-gh-api-for-template",
    "references-target-repo",
]


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(CHECK_NAMES, output_path)))


if __name__ == "__main__":
    main()
