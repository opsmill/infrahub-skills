#!/usr/bin/env python3
"""Grader for the check-proposed-change-commit eval.

The task asks for a bash script that gets open proposed changes re-validated
after a fixed check was merged to main. It reads `output.sh` and passes only
when the script moves the repository commit each proposed change runs: a
`git push` to each source branch after merging main into it. A loop of
`infrahubctl branch rebase` plus `CoreProposedChangeRunCheck` reruns the old
commit on branches synced with Git, a Git rebase onto main leaves the
repository sync unable to pull the branch, and a new branch and proposed
change re-validate main instead of the change under review.

No other managing-checks check grades a shell script, so this task runs the
one assertion on its own.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "moves-source-branch-commit",
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.yml"), sh_path=Path("output.sh"))))
