"""Shared grader library for the infrahub-analyzing-diagnostics skill.

Evals feed the model bundle excerpts inline and grade the findings report it
writes: each check inspects the report text for the skill's required moves
(manifest first, evidence citations, incident correlation, stable GitHub
search keys, read-only scope). Check functions take ``(text, **kwargs)`` and
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

# Characters of context inspected after each `gh search issues` occurrence —
# wide enough to cover a full command line including quoted keywords.
_SEARCH_WINDOW = 400

_MUTATING_PATTERNS = (
    r"docker(\s+compose)?\s+(down|restart|rm|kill|stop)",
    r"kubectl\s+(delete|scale|rollout\s+restart)",
    r"systemctl\s+(restart|stop)",
    r"rm\s+-rf",
)


def _gh_search_windows(text: str) -> list[str]:
    """Text windows following each `gh search issues` invocation."""
    return [
        text[m.start() : m.start() + _SEARCH_WINDOW]
        for m in re.finditer(r"gh\s+search\s+issues", text)
    ]


def check_mentions_manifest(text: str, **_: object) -> CheckResult:
    """Report reads/references the bundle manifest."""
    if re.search(r"bundle_information\.json|manifest", text, re.IGNORECASE):
        return True, "references the bundle manifest"
    return False, "no reference to bundle_information.json / manifest"


def check_mentions_version(text: str, *, version: str = "", **_: object) -> CheckResult:
    """The running Infrahub version from the bundle is stated in the report."""
    if not version:
        return False, "check_mentions_version requires version kwarg"
    if version in text:
        return True, f"states the running version {version}"
    return False, f"running version {version} not stated in the report"


def check_cites_bundle_evidence(text: str, **_: object) -> CheckResult:
    """Findings cite concrete bundle file paths as evidence."""
    if re.search(
        r"bundle/(logs|server|database|message-queue|cache|task-worker|task-manager|metrics)/",
        text,
    ):
        return True, "cites bundle paths as evidence"
    return False, "no bundle/<service>/ evidence path cited"


def check_restart_evidence(text: str, **_: object) -> CheckResult:
    """Report treats *.previous.log as restart/crash evidence."""
    has_previous = re.search(r"\.previous(\.log)?", text, re.IGNORECASE)
    has_restart = re.search(r"restart|crash|kill", text, re.IGNORECASE)
    if has_previous and has_restart:
        return True, "treats .previous.log as restart evidence"
    if not has_previous:
        return False, "does not mention the .previous.log file"
    return False, "mentions .previous.log but not the restart/crash it implies"


def check_incident_grouping(text: str, **_: object) -> CheckResult:
    """Signals are correlated into incidents with root vs cascade."""
    grouped = re.search(r"incident|correlat", text, re.IGNORECASE)
    chained = re.search(
        r"root[ -]cause|\broot\b|cascad|downstream|origin|trigger", text, re.IGNORECASE
    )
    if grouped and chained:
        return True, "correlates signals into incidents with a causal chain"
    if not grouped:
        return False, "no incident/correlation grouping found"
    return False, "grouping present but no root-vs-cascade distinction"


def check_mentions_all(text: str, *, terms: str = "", **_: object) -> CheckResult:
    """All comma-separated terms appear (case-insensitive)."""
    wanted = [t.strip() for t in terms.split(",") if t.strip()]
    if not wanted:
        return False, "check_mentions_all requires terms kwarg"
    low = text.lower()
    missing = [t for t in wanted if t.lower() not in low]
    if missing:
        return False, f"missing expected terms: {missing}"
    return True, f"mentions all of: {wanted}"


def check_github_search(text: str, **_: object) -> CheckResult:
    """Report includes a gh issue search against opsmill/infrahub."""
    if re.search(r"gh\s+search\s+issues", text) and "opsmill/infrahub" in text:
        return True, "searches opsmill/infrahub issues via gh"
    return False, "missing `gh search issues` against opsmill/infrahub"


def check_search_state_all(text: str, **_: object) -> CheckResult:
    """Issue search covers open AND closed issues."""
    if re.search(r"--state[= ]all", text):
        return True, "searches with --state all"
    return False, "search does not include closed issues (`--state all`)"


def check_search_keyword(text: str, *, keyword: str = "", **_: object) -> CheckResult:
    """A stable keyword appears in a gh search invocation."""
    if not keyword:
        return False, "check_search_keyword requires keyword kwarg"
    windows = _gh_search_windows(text)
    if not windows:
        return False, "no `gh search issues` command found"
    if any(keyword.lower() in w.lower() for w in windows):
        return True, f"search keys include `{keyword}`"
    return False, f"stable keyword `{keyword}` missing from search keys"


def check_search_excludes_token(text: str, *, token: str = "", **_: object) -> CheckResult:
    """A volatile token is stripped from every gh search invocation."""
    if not token:
        return False, "check_search_excludes_token requires token kwarg"
    windows = _gh_search_windows(text)
    if not windows:
        return False, "no `gh search issues` command found"
    if any(token.lower() in w.lower() for w in windows):
        return False, f"volatile token `{token}` leaked into a search query"
    return True, f"search keys exclude volatile token `{token}`"


def check_no_mutating_commands(text: str, **_: object) -> CheckResult:
    """Report stays read-only: no restart/delete/down commands."""
    hits = [p for p in _MUTATING_PATTERNS if re.search(p, text, re.IGNORECASE)]
    if hits:
        return False, f"report includes mutating commands: {hits}"
    return True, "no deployment-mutating commands"


def check_no_direct_issue_filing(text: str, **_: object) -> CheckResult:
    """Report does not file an issue itself (`gh issue create`).

    Mentions that negate the command ("do not run `gh issue create`") or
    attribute it to infrahub-reporting-issues are compliant in spirit —
    only a bare recommendation/invocation counts as filing directly.
    """
    for m in re.finditer(r"gh\s+issue\s+create", text):
        prefix = text[max(0, m.start() - 150) : m.start()]
        if re.search(
            r"\b(never|not|don'?t|doesn'?t|avoid|without|rather than|instead of)\b"
            r"|reporting-issues",
            prefix,
            re.IGNORECASE,
        ):
            continue
        return False, "report runs `gh issue create` (reporting-issues' job)"
    return True, "does not file an issue directly"


def check_cross_link_reporting_issues(text: str, **_: object) -> CheckResult:
    """Report hands off filing/commenting to infrahub-reporting-issues."""
    if re.search(r"reporting-issues", text, re.IGNORECASE):
        return True, "cross-links infrahub-reporting-issues"
    return False, "missing infrahub-reporting-issues cross-link"


CHECKS: dict[str, CheckFn] = {
    "mentions-manifest": check_mentions_manifest,
    "mentions-version": check_mentions_version,
    "cites-bundle-evidence": check_cites_bundle_evidence,
    "restart-evidence": check_restart_evidence,
    "incident-grouping": check_incident_grouping,
    "mentions-all": check_mentions_all,
    "github-search": check_github_search,
    "search-state-all": check_search_state_all,
    "search-keyword": check_search_keyword,
    "search-excludes-token": check_search_excludes_token,
    "no-mutating-commands": check_no_mutating_commands,
    "no-direct-issue-filing": check_no_direct_issue_filing,
    "cross-link-reporting-issues": check_cross_link_reporting_issues,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the model's report text; return skillgrade JSON."""
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
