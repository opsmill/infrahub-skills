#!/usr/bin/env python3
"""Grader script for the git-sync diagnostics bundle eval task.

Verifies a complete bundle was collected for a ``git-sync`` problem
category, including:

- Bundle root files (``manifest.yml``, ``README.md``)
- Baseline collection (versions, api-config, deployment, host, logs)
- No unredacted secrets anywhere in the bundle
- Multi-replica log coverage matches ``deployment.worker_replicas``
- ``flags.yml`` shape and the ``commit-not-found`` flag firing
- ``manifest.yml`` declares ``problem.category: git-sync``
- ``category/git-sync/`` exists and is non-empty

Usage::

    python check_git_sync_bundle.py <bundle-path>

Prints skillgrade JSON to stdout. Pass criterion is ``score == 1.0``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The hyphenated parent dir is not a Python package — import lib via sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = [
    "bundle-root",
    "baseline-present",
    "no-unredacted-secrets",
    "multi-replica-logs",
    "flags-yml-shape",
    ("manifest-category", {"category": "git-sync"}),
    ("category-dir-present", {"category": "git-sync"}),
    ("flag-fired", {"flag_id": "commit-not-found"}),
]


def main() -> None:
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_bundle")
    result = run_checks(CHECKS, bundle)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
