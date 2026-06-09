"""Shared grader library for infrahub-managing-objects skill evaluations.

Most managing-objects tasks produce object YAML, but the branch-first
workflow task produces a load *plan* (Markdown/commands), not a single
object file. Checks here scan the raw text for the safe-loading workflow:
loading onto a dedicated branch rather than the default branch, and routing
the change through review before it reaches the default branch.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["recommends-branch", "explains-default-branch-risk-or-review"],
        Path("output.md"),
    )
    print(result)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Output loading
# ---------------------------------------------------------------------------


def load_output(path: Path) -> str:
    """Read the model's output file as text."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Branch-first workflow checks
# ---------------------------------------------------------------------------


# The load/CRUD should be scoped to a dedicated branch. Any of these is a
# strong signal the plan keeps the write off the default branch: an explicit
# `--branch` flag, a `branch create` step, or prose that puts the work on a
# branch.
_BRANCH_PATTERNS = [
    re.compile(r"--branch\b", re.IGNORECASE),
    re.compile(r"\bbranch\s+create\b", re.IGNORECASE),
    re.compile(r"\bcreate\s+(?:a\s+)?(?:new\s+)?branch\b", re.IGNORECASE),
    re.compile(r"\b(?:on|onto|to|use|using|in|via|a)\s+(?:a\s+)?(?:new\s+|named\s+|feature\s+|separate\s+)?branch\b", re.IGNORECASE),
    re.compile(r"\bbranch[-_]?(?:name|first)\b", re.IGNORECASE),
]


def check_recommends_branch(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if the plan does not scope the load/CRUD to a branch."""
    for pat in _BRANCH_PATTERNS:
        if pat.search(text):
            return True, f"Recommends a branch (matched {pat.pattern!r})"
    return False, "Does not recommend loading onto a branch"


# The plan should make clear the dedicated branch is the safe alternative to
# the default branch: cautioning against writing straight to the default
# branch (named generically, or by its conventional name `main`), routing the
# change through the proposed-change / merge review path, or noting the branch
# is discardable.
_DEFAULT_BRANCH_RISK_PATTERNS = [
    # Cautioning against writing to the default branch (generic phrasing)
    re.compile(r"\b(?:not|instead of|rather than|avoid|without|never|off)\b[^.\n]{0,40}\bdefault\s+branch\b", re.IGNORECASE),
    re.compile(r"\b(?:directly|straight)\s+(?:in)?to\s+(?:the\s+)?default\s+branch\b", re.IGNORECASE),
    # Cautioning against writing to the default branch by its conventional name
    re.compile(r"\b(?:not|instead of|rather than|avoid|without|never|off)\b[^.\n]{0,40}\bmain\b", re.IGNORECASE),
    re.compile(r"\b(?:directly|straight)\s+(?:in)?to\s+(?:the\s+)?`?main`?\b", re.IGNORECASE),
    # The review / merge path that a branch enables
    re.compile(r"\bproposed[-\s]?change\b", re.IGNORECASE),
    re.compile(r"\bmerge\b", re.IGNORECASE),
    # The branch is cheap to throw away
    re.compile(r"\bdiscard\b", re.IGNORECASE),
    re.compile(r"\bthrow\s+(?:it\s+)?away\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+the\s+branch\b", re.IGNORECASE),
]


def check_explains_default_branch_risk_or_review(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if the plan neither warns about the default branch nor routes through review."""
    for pat in _DEFAULT_BRANCH_RISK_PATTERNS:
        if pat.search(text):
            return True, f"Explains default-branch risk / review path (matched {pat.pattern!r})"
    return False, "Does not caution against the default branch or mention the review/merge/discard path"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------


CHECKS = {
    "recommends-branch": check_recommends_branch,
    "explains-default-branch-risk-or-review": check_explains_default_branch_risk_or_review,
}


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against the output file and return skillgrade JSON."""
    text = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(text)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    if failed:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}


if __name__ == "__main__":  # pragma: no cover
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(list(CHECKS.keys()), out), indent=2))
