"""Shared grader library for the infrahub-collecting-diagnostics skill.

The rewritten skill recommends a sequence of ``infrahub-collect`` commands
rather than producing a bundle directory. Evals therefore grade the model's
plan text: each check inspects the recommended-commands output for the right
invocation, flags, and cautions. Check functions take ``(text, **kwargs)`` and
return ``(passed, message)``. Return shape matches sibling grader libs so
skillgrade ingests it identically.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

CheckResult = tuple[bool, str]
CheckFn = Callable[..., CheckResult]


def check_mentions_create(text: str, **_: object) -> CheckResult:
    """Plan recommends `infrahub-collect create`."""
    if re.search(r"infrahub-collect\s+create", text):
        return True, "recommends `infrahub-collect create`"
    return False, "missing `infrahub-collect create` invocation"


def check_mentions_env_detect(text: str, **_: object) -> CheckResult:
    """Plan recommends `infrahub-collect environment detect`."""
    if re.search(r"infrahub-collect\s+environment\s+detect", text):
        return True, "recommends `environment detect`"
    return False, "missing `infrahub-collect environment detect`"


def check_mentions_flag(text: str, *, flag: str = "", **_: object) -> CheckResult:
    """A specific create flag appears in the plan."""
    if not flag:
        return False, "check_mentions_flag requires flag kwarg"
    # Match the flag as a whole token (e.g. --benchmark, not --benchmarking).
    if re.search(rf"(?<!\S){re.escape(flag)}(?!\w)", text):
        return True, f"plan includes `{flag}`"
    return False, f"expected flag `{flag}` not found"


def check_review_before_sharing(text: str, **_: object) -> CheckResult:
    """Plan surfaces a review-before-sharing caution."""
    low = text.lower()
    has_review = "review" in low and ("shar" in low or "send" in low or "bundle" in low)
    has_mask_gap = "key name" in low or "key-name" in low or "mask" in low or "redact" in low
    if has_review or has_mask_gap:
        return True, "surfaces review-before-sharing caution"
    return False, "no review-before-sharing caution found"


def check_cross_link_reporting_issues(text: str, **_: object) -> CheckResult:
    """Plan cross-links the reporting-issues skill for public issues."""
    if re.search(r"reporting-issues", text, re.IGNORECASE):
        return True, "cross-links infrahub-reporting-issues"
    return False, "missing infrahub-reporting-issues cross-link"


def check_no_legacy_artifacts(text: str, **_: object) -> CheckResult:
    """Plan does NOT resurrect the old hand-rolled artifacts."""
    legacy = ("manifest.yml", "flags.yml", "redaction-report.txt", "infrahubctl telemetry")
    hits = [name for name in legacy if name in text]
    if hits:
        return False, f"plan references retired artifacts: {hits}"
    return True, "no legacy hand-rolled artifacts referenced"


CHECKS: dict[str, CheckFn] = {
    "mentions-create": check_mentions_create,
    "mentions-env-detect": check_mentions_env_detect,
    "mentions-flag": check_mentions_flag,
    "review-before-sharing": check_review_before_sharing,
    "cross-link-reporting-issues": check_cross_link_reporting_issues,
    "no-legacy-artifacts": check_no_legacy_artifacts,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the model's plan text; return skillgrade JSON."""
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
        except Exception as exc:  # pragma: no cover — defensive
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
