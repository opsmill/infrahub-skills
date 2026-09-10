#!/usr/bin/env python3
"""Grader for the check-shared-module eval.

Grades three artifacts at once, because the shared-module pattern is only
correct as a set: the check must import the package absolutely, the image must
install it into the base virtualenv without wiping that environment, and the
`.infrahub.yml` must declare the dependency so artifacts regenerate when the
shared logic changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "shared-module-absolute-import",
    "dockerfile-targets-base-venv",
    "dockerfile-uv-sync-inexact",
    "watch-declares-shared-package",
]

if __name__ == "__main__":
    print(
        json.dumps(
            run_checks(
                CHECKS,
                Path("output.yml"),
                py_path=Path("output.py"),
                dockerfile_path=Path("output.dockerfile"),
            )
        )
    )
