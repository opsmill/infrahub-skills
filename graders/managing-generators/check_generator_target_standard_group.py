#!/usr/bin/env python3
"""Grader for the generator-target-standard-group eval.

The answer is an ``output.md`` holding each file the model writes in its own
```yaml fence. The new assertion reads the whole answer. The two baseline
watch checks read the ``generator_definitions`` entries pulled out of it, so
the task also catches a regression in the neighbouring watch rule.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import (  # noqa: E402
    CHECKS,
    load_output,
    manifest_generator_entries,
    yaml_documents,
)

ANSWER_CHECKS = ["generator-targets-existing-group"]
MANIFEST_CHECKS = ["gen-watch-present", "gen-watch-object-form"]


def grade(path: Path) -> dict:
    output = load_output(path)
    manifest = {
        "generator_definitions": manifest_generator_entries(
            yaml_documents(output["raw"])
        )
    }
    entries = []
    for names, arg in ((ANSWER_CHECKS, output), (MANIFEST_CHECKS, manifest)):
        for name in names:
            try:
                ok, msg = CHECKS[name](arg)
            except Exception as exc:  # never let one check crash all
                ok, msg = False, f"Error running check: {exc}"
            entries.append({"name": name, "passed": ok, "message": msg})

    passed = sum(e["passed"] for e in entries)
    total = len(entries)
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    return {"score": round(passed / total, 4), "details": details, "checks": entries}


if __name__ == "__main__":
    print(json.dumps(grade(Path("output.md"))))
