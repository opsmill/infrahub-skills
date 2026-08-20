#!/usr/bin/env python3
"""Grader for the level-2 bug-vs-feature-vs-docs-gap classification eval.

Which checks run, and what `states-bug-or-feature` treats as the correct
answer, are both driven by `--expected-kind`, never by sniffing the
drafted output's own title tag. Choosing the rubric from the model's own
tag would let a self-consistent wrong answer (tag matches its own stated
conclusion, but that conclusion is simply the wrong one for this
scenario) score full marks under the rubric it picked for itself. Each
level-2 eval task knows which kind its own scenario's evidence supports
and passes it explicitly.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

# Maps the CLI's kind key to the check list a scenario of that kind
# should be graded on, and to the `expected_kind` label
# `states-bug-or-feature` compares the drafted output's stated kind
# against. `cites-escape-as-feature-evidence` only makes sense for a
# feature expectation (it requires an escape tied specifically to a
# feature conclusion); a docs-gap scenario is graded on
# `cites-escape-outcome` instead (did the output say whether the escape
# resolved the problem), which is *always* included for a docs-gap
# scenario regardless of what tag the model actually drafted, so its
# coverage no longer depends on the model happening to emit `bug(docs):`.
# A bug scenario keeps `cites-escape-as-feature-evidence` too: it passes
# vacuously when no escape is present, which is the common case for a
# bug (the rule already covers the topic, so there is usually nothing to
# escape to), and still fires correctly if a bug-scenario draft narrates
# an undisqualified escape it should not have.
CHECKS_BY_KIND = {
    "bug": [
        ("states-bug-or-feature", {"expected_kind": "bug"}),
        "justifies-kind-by-coverage",
        "cites-escape-as-feature-evidence",
    ],
    "feature": [
        ("states-bug-or-feature", {"expected_kind": "feature"}),
        "justifies-kind-by-coverage",
        "cites-escape-as-feature-evidence",
    ],
    "docs-gap": [
        ("states-bug-or-feature", {"expected_kind": "docs gap"}),
        "justifies-kind-by-coverage",
        "cites-escape-outcome",
    ],
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="output.md")
    parser.add_argument(
        "--expected-kind",
        required=True,
        choices=sorted(CHECKS_BY_KIND),
        help="the kind this scenario's own evidence actually supports",
    )
    args = parser.parse_args()
    print(json.dumps(run_checks(CHECKS_BY_KIND[args.expected_kind], Path(args.output))))
