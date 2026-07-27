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

_MUTATING_PATTERNS = (
    r"docker(\s+compose)?\s+(down|restart|rm|kill|stop)",
    r"kubectl\s+(delete|scale|rollout\s+restart)",
    r"systemctl\s+(restart|stop)",
    r"rm\s+-rf",
)

_BUNDLE_PATH = (
    r"bundle/(?:logs|server|database|message-queue|cache|task-worker"
    r"|task-manager|metrics)/"
)

# Words that negate or hand off the action they precede — reports may quote a
# command while forbidding or recommending it without the analysis running it.
_NEGATION_WORDS = (
    r"\b(never|not|don'?t|doesn'?t|won'?t|wouldn'?t|avoid|without"
    r"|rather than|instead of)\b"
)


def _gh_search_commands(text: str) -> list[str]:
    """The full command line of each `gh search issues` invocation.

    The command line is the query surface; prose around it (e.g. "stripped
    the hostname X from the key") legitimately names volatile tokens.
    """
    return [m.group(0) for m in re.finditer(r"gh\s+search\s+issues[^\n]*", text)]


def _root_windows(text: str) -> list[str]:
    """The text of each root-mention line plus its continuation line.

    The report template anchors the root to its evidence on the `- Root:` line
    (path) and the line below (quoted excerpt); a wider window would credit
    unrelated paths mentioned further down the section.
    """
    windows: list[str] = []
    for m in re.finditer(r"(?i)\broot(?:[ -]cause)?\b|caused by", text):
        line_end = text.find("\n", m.end())
        if line_end == -1:
            windows.append(text[m.end() :])
            continue
        next_end = text.find("\n", line_end + 1)
        windows.append(text[m.end() : len(text) if next_end == -1 else next_end])
    return windows


def _incident_sections(text: str) -> list[tuple[str, str]]:
    """(heading line, body) for each `## Incident ...` section in the report."""
    matches = list(re.finditer(r"(?im)^#{1,6}\s*incident\b[^\n]*", text))
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(0), text[m.end() : end]))
    return sections


def check_asks_bundle_location(text: str, **_: object) -> CheckResult:
    """Response asks where the bundle is BEFORE any analysis content.

    The question must be about the bundle itself — a closing "where should I
    save the report?" does not satisfy the user-gate.
    """
    if "bundle" not in text.lower():
        return False, "response never mentions the bundle"
    # A sentence may wrap across lines — stop only at sentence enders.
    for m in re.finditer(r"[^.!?]*\?", text):
        sentence = m.group(0)
        if not re.search(r"where|path|location|director|folder", sentence, re.IGNORECASE):
            continue
        if not re.search(r"bundle", sentence, re.IGNORECASE):
            continue
        preceding = text[: m.start()]
        if re.search(
            r"(?im)^#{1,6}\s*(incident|finding)\b|bundle/logs/|root[ -]cause",
            preceding,
        ):
            return False, "analysis content precedes the bundle-location question"
        return True, "asks for the bundle location before analyzing"
    return False, "does not ask where the bundle is"


def check_no_location_scan(text: str, **_: object) -> CheckResult:
    """Response neither scans for the bundle nor assumes its location.

    Negated mentions ("I won't assume the default") and mentions inside a
    question ("is it in ./infrahub_bundles/, or elsewhere?") are compliant —
    only an actual scan command or an affirmative use of a location counts.
    """
    # Command-shaped scans: the verb takes a path/flag/glob argument, or
    # directly targets the bundle directory/manifest.
    scan_patterns = (
        r"\b(find|ls|locate|glob)\s+[.~/*'\"-][^\n]*(infrahub_bundles|bundle_information)",
        r"\b(find|ls|locate|glob)\s+\S*(infrahub_bundles|bundle_information)",
    )
    for pattern in scan_patterns:
        for m in re.finditer(pattern, text):
            prefix = text[max(0, m.start() - 150) : m.start()]
            if re.search(_NEGATION_WORDS, prefix, re.IGNORECASE):
                continue
            return False, "scans the filesystem for the bundle instead of asking"
    # Assumptions phrased with "assume".
    for m in re.finditer(
        r"assum\w+[^\n]{0,40}(default|infrahub_bundles|location|path)", text, re.IGNORECASE
    ):
        prefix = text[max(0, m.start() - 150) : m.start()]
        if re.search(_NEGATION_WORDS, prefix, re.IGNORECASE):
            continue
        return False, "assumes a bundle location instead of asking"
    # Assumptions phrased without "assume": an affirmative action verb
    # applied to the default directory, outside a question. The gap may
    # cross a wrapped line or a path dot (`./`) but not a sentence ender.
    for m in re.finditer(
        r"\b(read\w*|scan\w*|look\w*|going to|start\w*|proceed\w*|analyz\w*"
        r"|check\w*|open\w*|us(?:e|ing)|found|grab\w*|pick\w*)\b"
        r"(?:[^.!?]|\.(?=/)){0,80}infrahub_bundles",
        text,
        re.IGNORECASE,
    ):
        tail = text[m.end() : m.end() + 120]
        sentence_end = re.search(r"[.!?]", tail)
        if sentence_end and sentence_end.group(0) == "?":
            continue  # the mention lives in a question — that's asking
        # Negation must target this verb ("won't read ...") — a wider window
        # would let an unrelated "not" ("you did not pass --output-dir, so I
        # am going to read the default") exempt the assumption.
        prefix = text[max(0, m.start() - 15) : m.start()]
        if re.search(_NEGATION_WORDS, prefix, re.IGNORECASE):
            continue
        return False, "uses the default bundle directory instead of asking"
    return True, "no location scanning or assumed default"


def check_mentions_manifest(text: str, **_: object) -> CheckResult:
    """Report reads/references the bundle manifest."""
    if re.search(r"bundle_information\.json|manifest", text, re.IGNORECASE):
        return True, "references the bundle manifest"
    return False, "no reference to bundle_information.json / manifest"


def check_mentions_version(text: str, *, version: str = "", **_: object) -> CheckResult:
    """The running Infrahub version from the bundle is stated in the report."""
    if not version:
        return False, "check_mentions_version requires version kwarg"
    # Boundary guards so 1.2.4 is not satisfied by 11.2.42 or 1.2.42.
    if re.search(rf"(?<![\d.]){re.escape(version)}(?!\d)(?!\.\d)", text):
        return True, f"states the running version {version}"
    return False, f"running version {version} not stated in the report"


def check_cites_bundle_evidence(text: str, **_: object) -> CheckResult:
    """Findings cite bundle paths — in every incident section when present."""
    if not re.search(_BUNDLE_PATH, text):
        return False, "no bundle/<service>/ evidence path cited"
    uncited = [
        head.strip()
        for head, body in _incident_sections(text)
        if not re.search(r"bundle/", body)
    ]
    if uncited:
        return False, f"incident section(s) citing no bundle path: {uncited[:2]}"
    return True, "bundle paths cited as evidence (per incident where sectioned)"


def check_restart_evidence(text: str, **_: object) -> CheckResult:
    """Report treats *.previous.log as restart/crash evidence."""
    has_previous = re.search(r"\.previous(\.log)?", text, re.IGNORECASE)
    has_restart = re.search(r"restart|crash|kill", text, re.IGNORECASE)
    if has_previous and has_restart:
        return True, "treats .previous.log as restart evidence"
    if not has_previous:
        return False, "does not mention the .previous.log file"
    return False, "mentions .previous.log but not the restart/crash it implies"


def check_incident_grouping(
    text: str, *, max_incidents: int = 0, **_: object
) -> CheckResult:
    """Signals correlate into incident sections with a root anchored to evidence.

    ``max_incidents`` caps the section count for scenarios whose signals are
    known to collapse — more sections than that is a flat error list wearing
    incident headings.
    """
    headings = _incident_sections(text)
    if not headings:
        return False, "no `## Incident` sections — signals not grouped into incidents"
    if max_incidents and len(headings) > max_incidents:
        return False, (
            f"{len(headings)} incident sections where the signals correlate into "
            f"at most {max_incidents} — flat error list, not a correlation"
        )
    if not any("bundle/" in w for w in _root_windows(text)):
        return False, "no root error anchored to a bundle path"
    if not re.search(r"(?i)cascad\w+|downstream|knock-on|secondary|consequen\w+", text):
        return False, "root named but cascade/downstream effects not distinguished"
    return True, (
        f"{len(headings)} incident section(s); root anchored to bundle evidence, "
        "cascade distinguished"
    )


def check_severity_labels(text: str, **_: object) -> CheckResult:
    """Every incident section carries a severity from the report's scale."""
    sections = _incident_sections(text)
    if not sections:
        return False, "no incident sections to carry a severity"
    missing = [
        head.strip()
        for head, body in sections
        if not re.search(r"(?i)\b(critical|high|medium|low)\b", head + body)
    ]
    if missing:
        return False, f"incident section(s) without a severity label: {missing[:2]}"
    return True, "every incident carries a severity label"


def check_root_service(text: str, *, service: str = "", **_: object) -> CheckResult:
    """The incident's root is attributed to the named service."""
    if not service:
        return False, "check_root_service requires service kwarg"
    for window in _root_windows(text):
        if re.search(re.escape(service), window, re.IGNORECASE):
            return True, f"root attributed to {service}"
    return False, f"incident root not attributed to {service}"


def check_mentions_all(text: str, *, terms: str = "", **_: object) -> CheckResult:
    """All comma-separated terms appear (case-insensitive).

    Purely numeric terms are matched with digit boundaries so `480` is not
    satisfied by `4800` or a timestamp fragment.
    """
    wanted = [t.strip() for t in terms.split(",") if t.strip()]
    if not wanted:
        return False, "check_mentions_all requires terms kwarg"
    low = text.lower()
    missing = []
    for t in wanted:
        if t.isdigit():
            if not re.search(rf"(?<!\d){re.escape(t)}(?!\d)", text):
                missing.append(t)
        elif t.lower() not in low:
            missing.append(t)
    if missing:
        return False, f"missing expected terms: {missing}"
    return True, f"mentions all of: {wanted}"


def check_evaluates_benchmark(text: str, **_: object) -> CheckResult:
    """Report evaluates collected benchmark results (single-CPU + IOPS)."""
    low = text.lower()
    if "benchmark" not in low:
        return False, "benchmark results never mentioned"
    if not re.search(r"single[- ]?(cpu|core|thread)", low):
        return False, "single-CPU score not evaluated"
    if "iops" not in low:
        return False, "storage IOPS not evaluated"
    return True, "evaluates single-CPU score and storage IOPS"


def check_recommends_benchmark(text: str, **_: object) -> CheckResult:
    """Report recommends a --benchmark bundle and says what it answers."""
    if not re.search(r"(?<!\w)--benchmark(?![\w-])", text):
        return False, "does not recommend `--benchmark`"
    low = text.lower()
    if re.search(r"single[- ]?(cpu|core|thread)", low) and "iops" in low:
        return True, "recommends `--benchmark` for single-CPU score and IOPS"
    return False, "recommends `--benchmark` without the single-CPU/IOPS rationale"


def check_edition_cap(text: str, **_: object) -> CheckResult:
    """Report ties load-correlated slowness to the edition question."""
    low = text.lower()
    if "community" not in low:
        return False, "does not name the Community edition"
    if not re.search(r"concurren|parallel|load", low):
        return False, "does not tie the slowness to concurrent load"
    if "enterprise" not in low and "opsmill" not in low:
        return False, "does not raise the edition question (Enterprise / OpsMill)"
    return True, "raises the edition question for load-correlated slowness"


def check_cross_link_collecting_diagnostics(text: str, **_: object) -> CheckResult:
    """Report hands re-collection back to infrahub-collecting-diagnostics."""
    if re.search(r"collecting-diagnostics|infrahub-collect\b", text, re.IGNORECASE):
        return True, "cross-links infrahub-collecting-diagnostics"
    return False, "missing infrahub-collecting-diagnostics cross-link"


def check_github_search(text: str, **_: object) -> CheckResult:
    """Report includes a gh issue search against opsmill/infrahub."""
    if re.search(r"gh\s+search\s+issues", text) and "opsmill/infrahub" in text:
        return True, "searches opsmill/infrahub issues via gh"
    return False, "missing `gh search issues` against opsmill/infrahub"


def check_search_keyword(text: str, *, keyword: str = "", **_: object) -> CheckResult:
    """A stable keyword appears in a gh search invocation."""
    if not keyword:
        return False, "check_search_keyword requires keyword kwarg"
    commands = _gh_search_commands(text)
    if not commands:
        return False, "no `gh search issues` command found"
    if any(keyword.lower() in c.lower() for c in commands):
        return True, f"search keys include `{keyword}`"
    return False, f"stable keyword `{keyword}` missing from search keys"


def check_search_excludes_token(text: str, *, token: str = "", **_: object) -> CheckResult:
    """A volatile token is stripped from every gh search command line.

    Prose around the command may name the token (e.g. documenting what was
    stripped) — only the command line itself is the query surface.
    """
    if not token:
        return False, "check_search_excludes_token requires token kwarg"
    commands = _gh_search_commands(text)
    if not commands:
        return False, "no `gh search issues` command found"
    if any(token.lower() in c.lower() for c in commands):
        return False, f"volatile token `{token}` leaked into a search query"
    return True, f"search keys exclude volatile token `{token}`"


def check_no_mutating_commands(text: str, **_: object) -> CheckResult:
    """Report stays read-only: no restart/delete/down commands.

    Naming a command inside a negation ("do not run ...") or an explicitly
    not-executed recommendation is compliant — the rule bans the analysis
    *running* mutations, not mentioning them.
    """
    for pattern in _MUTATING_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            prefix = text[max(0, m.start() - 200) : m.start()]
            if re.search(
                _NEGATION_WORDS + r"|recommend\w*|for you to run|not execut\w+",
                prefix,
                re.IGNORECASE,
            ):
                continue
            return False, f"report includes a mutating command: `{m.group(0)}`"
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
            _NEGATION_WORDS + r"|reporting-issues",
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
    "asks-bundle-location": check_asks_bundle_location,
    "no-location-scan": check_no_location_scan,
    "mentions-manifest": check_mentions_manifest,
    "mentions-version": check_mentions_version,
    "cites-bundle-evidence": check_cites_bundle_evidence,
    "restart-evidence": check_restart_evidence,
    "incident-grouping": check_incident_grouping,
    "severity-labels": check_severity_labels,
    "root-service": check_root_service,
    "mentions-all": check_mentions_all,
    "evaluates-benchmark": check_evaluates_benchmark,
    "recommends-benchmark": check_recommends_benchmark,
    "edition-cap": check_edition_cap,
    "cross-link-collecting-diagnostics": check_cross_link_collecting_diagnostics,
    "github-search": check_github_search,
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
