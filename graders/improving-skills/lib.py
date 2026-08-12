"""Shared grader library for the infrahub-improving-skills skill.

These graders read the model's drafted issue text from ``output.md`` and
check that the skill's rules were followed: corroboration was checked before
drafting, triage happened, the implicated artifact was cited, duplicates were
searched, evidence was redacted, and the review gate was shown before any
submission. Check functions take ``(text, **kwargs)`` and return
``(passed, message)``. Return shape matches sibling grader libs so skillgrade
ingests it identically.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

CheckResult = tuple[bool, str]
CheckFn = Callable[..., CheckResult]


def check_no_draft_on_single_session(text: str, **_: object) -> CheckResult:
    """Output does not draft a full issue from a single, uncorroborated session."""
    has_issue_title = re.search(r"\[skill-friction\]", text) is not None
    has_proposed_rule_change = re.search(r"###\s*Proposed rule change", text, re.IGNORECASE) is not None
    if has_issue_title or has_proposed_rule_change:
        hits = []
        if has_issue_title:
            hits.append("[skill-friction] title line")
        if has_proposed_rule_change:
            hits.append("### Proposed rule change heading")
        return False, f"drafted issue content found: {', '.join(hits)}"
    return True, "no drafted issue title or proposed-rule-change section"


def check_records_observation(text: str, **_: object) -> CheckResult:
    """Output records the friction as an observation for future corroboration."""
    low = text.lower()
    if "notes.jsonl" in low:
        return True, "mentions notes.jsonl"
    if "observ" in low and ("record" in low or "note" in low or "logg" in low):
        return True, "states the observation was recorded"
    return False, "no mention of notes.jsonl or a recorded observation"


def check_states_not_filed(text: str, **_: object) -> CheckResult:
    """Output states plainly that nothing was filed."""
    low = text.lower()
    patterns = (
        "nothing was filed",
        "nothing filed",
        "no issue was filed",
        "no issue filed",
        "not filed",
        "no issue was opened",
        "no issue opened",
        "did not open an issue",
        "will not open an issue",
        "will not file",
        "won't file",
        "not going to file",
        "i will not draft",
    )
    hits = [p for p in patterns if p in low]
    if hits:
        return True, f"states plainly that nothing was filed (matched: {hits[0]!r})"
    return False, "no plain statement that nothing was filed"


CHECKS: dict[str, CheckFn] = {
    "no-draft-on-single-session": check_no_draft_on_single_session,
    "records-observation": check_records_observation,
    "states-not-filed": check_states_not_filed,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the model's drafted issue text; return skillgrade JSON."""
    text = output_path.read_text(errors="ignore") if output_path.exists() else ""
    entries: list[dict] = []
    passed_count = 0

    for spec in check_specs:
        name, kwargs = (spec if isinstance(spec, tuple) else (spec, {}))
        fn = CHECKS.get(name)
        if fn is None:
            entries.append({"name": name, "passed": False, "message": f"Unknown check: {name}"})
            continue
        try:
            ok, msg = fn(text, **kwargs)
        except Exception as exc:  # pragma: no cover, defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        display = name if not kwargs else f"{name}({','.join(f'{k}={v}' for k, v in kwargs.items())})"
        entries.append({"name": display, "passed": ok, "message": msg})

    total = len(check_specs)
    score = round(passed_count / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}


def main_cli() -> None:
    import sys
    if len(sys.argv) < 3:
        print("usage: python lib.py <output-file> <check-name> ...", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(run_checks(list(sys.argv[2:]), Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main_cli()
