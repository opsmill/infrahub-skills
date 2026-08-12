#!/usr/bin/env python3
"""Grader for the level-2 bug-vs-feature-vs-docs-gap classification eval."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import _TITLE_TAG_RE, run_checks  # noqa: E402

CHECKS = [
    "states-bug-or-feature",
    "justifies-kind-by-coverage",
    "cites-escape-as-feature-evidence",
]

# A `docs:` draft is not asking the same question as a `feat:` draft:
# `cites-escape-as-feature-evidence` requires the output to tie its escape
# to a feature conclusion, which a compliant docs-gap draft never states
# (it says the escape failed, not that it resolved into a feature), so
# that check would fail a correct docs-gap output outright. In its place,
# a docs-gap draft is graded on `cites-escape-outcome`: did it say whether
# the escape resolved the problem or not, the sentence the whole
# feature/docs-gap split rests on. bug:/feat: drafts keep the original
# three-check list completely unchanged.
DOCS_GAP_CHECKS = [
    "states-bug-or-feature",
    "justifies-kind-by-coverage",
    "cites-escape-outcome",
]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    text = out.read_text(errors="ignore") if out.exists() else ""
    tag_match = _TITLE_TAG_RE.search(text)
    is_docs = bool(tag_match and tag_match.group(1).lower() == "docs")
    checks = DOCS_GAP_CHECKS if is_docs else CHECKS
    print(json.dumps(run_checks(checks, out)))
