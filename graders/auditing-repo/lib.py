"""Shared grader library for infrahub-auditing-repo skill evaluations.

Unlike ``graders/managing-schemas/lib.py``, whose CHECKS registry maps
flat string keys to no-argument check functions, this library's checks
are parameterised over ``(rule_name, expected_value)`` tuples. To keep
the per-grader scripts tiny (a short list of check names plus
``run_checks``), the registry uses colon-encoded keys
(``yagni-finding-severity:<rule>:<sev>``) that ``_dispatch`` splits and
passes to the underlying function. This avoids exposing closures or
helper builders in every grader file.

The model is prompted to emit the audit findings as JSON to ``output.json``
in the cwd. Each finding is a dict with the keys this library inspects:

    {
        "rule": "yagni-python-validator-vs-schema-constraint",
        "severity": "HIGH",
        "ladder_step": 3,
        "file": "checks/check_vpn_unique.py",
        "line": "12"
    }

Findings may carry additional fields; this library ignores anything it
does not specifically check.

Each check function returns ``(bool, str)`` — the bool indicates pass/fail,
the string is a one-line message that ends up in the skillgrade report.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["yagni-finding-present:yagni-python-validator-vs-schema-constraint",
         "yagni-finding-severity:yagni-python-validator-vs-schema-constraint:MEDIUM",
         "yagni-finding-ladder-step:yagni-python-validator-vs-schema-constraint:3"],
        Path("output.json"),
    )
    print(result)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------


def load_output(path: Path) -> tuple[list[dict], str]:
    """Load the audit-findings JSON file.

    Returns a tuple of ``(findings_list, raw_text)``.

    The model may emit either:
      - A bare list of findings: ``[{"rule": ..., ...}, ...]``
      - An object wrapping the findings: ``{"findings": [...], ...}``
      - The full report shape: ``{"summary": {...}, "findings": [...]}``

    All three are normalised to the list form. If the file is missing or
    unparseable, returns ``([], raw_text)`` — checks downstream will
    naturally fail with "finding missing" messages.
    """
    if not path.exists():
        return [], ""
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], raw

    if isinstance(data, list):
        return data, raw
    if isinstance(data, dict):
        findings = data.get("findings", [])
        if isinstance(findings, list):
            return findings, raw
    return [], raw


def _find(findings: list[dict], rule: str) -> dict | None:
    """Return the first finding matching the given rule name, or None."""
    for f in findings:
        if isinstance(f, dict) and f.get("rule") == rule:
            return f
    return None


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_yagni_finding_present(findings: list[dict], rule: str) -> tuple[bool, str]:
    """Assert the named yagni-* rule appears at least once in findings."""
    if _find(findings, rule) is not None:
        return True, f"{rule} found"
    rules_seen = sorted({f.get("rule", "<no-rule>") for f in findings if isinstance(f, dict)})
    return False, f"{rule} missing. Saw: {rules_seen}"


def check_yagni_finding_severity(
    findings: list[dict], rule: str, expected: str
) -> tuple[bool, str]:
    """Assert the named rule's finding carries the expected severity."""
    f = _find(findings, rule)
    if f is None:
        return False, f"{rule} missing — cannot check severity"
    actual = f.get("severity", "<missing>")
    if str(actual).upper() == expected.upper():
        return True, f"{rule} severity={actual}"
    return False, f"{rule} severity={actual}, expected {expected}"


def check_yagni_finding_ladder_step(
    findings: list[dict], rule: str, expected: int
) -> tuple[bool, str]:
    """Assert the named rule's finding carries the expected ladder_step."""
    f = _find(findings, rule)
    if f is None:
        return False, f"{rule} missing — cannot check ladder_step"
    actual = f.get("ladder_step")
    if actual == expected:
        return True, f"{rule} ladder_step={actual}"
    return False, f"{rule} ladder_step={actual}, expected {expected}"


def check_yagni_findings_sorted_by_ladder(findings: list[dict]) -> tuple[bool, str]:
    """Assert all yagni-* findings come out in ascending ladder_step order."""
    yagni = [
        f for f in findings
        if isinstance(f, dict) and str(f.get("rule", "")).startswith("yagni-")
    ]
    if not yagni:
        return False, "no yagni-* findings emitted"
    steps = [f.get("ladder_step", -1) for f in yagni]
    if steps != sorted(steps):
        return False, f"yagni findings out of ladder order: {steps}"
    return True, f"yagni findings sorted by ladder_step: {steps}"


def check_yagni_no_finding_above_medium(findings: list[dict]) -> tuple[bool, str]:
    """Class-level severity cap: every yagni-* finding must be MEDIUM or LOW.

    YAGNI rules are advisory — the code works, the schema loads, the
    pipeline passes. The audit's severity legend reserves CRITICAL and
    HIGH for broken refs, silent failures, and deprecated fields. This
    check enforces the cap across the whole finding set so a new yagni
    rule added without updating its per-rule grader can't silently
    introduce a HIGH-severity finding.
    """
    ALLOWED = {"MEDIUM", "LOW"}
    offenders = [
        f for f in findings
        if isinstance(f, dict)
        and str(f.get("rule", "")).startswith("yagni-")
        and str(f.get("severity", "")).upper() not in ALLOWED
    ]
    if offenders:
        details = [f"{f.get('rule')}={f.get('severity')}" for f in offenders]
        return False, f"yagni severity cap violated (MEDIUM max): {details}"
    return True, "all yagni findings at MEDIUM or below"


def check_yagni_finding_carves_out_bootstrap(
    findings: list[dict], bootstrap_path_substring: str = "bootstrap"
) -> tuple[bool, str]:
    """Assert no yagni-generator-hardcoding-data finding fires on a bootstrap path."""
    offenders = [
        f for f in findings
        if isinstance(f, dict)
        and f.get("rule") == "yagni-generator-hardcoding-data"
        and bootstrap_path_substring in str(f.get("file", ""))
    ]
    if offenders:
        return False, f"bootstrap carve-out violated on: {[f.get('file') for f in offenders]}"
    return True, "bootstrap carve-out respected"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------
#
# Keys use a colon-separated form to encode the rule (and any expected
# value) the check is being parameterised with. The dispatcher in
# ``run_checks`` splits on the first one or two colons.

_BASE_CHECKS: dict[str, Any] = {
    "yagni-finding-present": check_yagni_finding_present,
    "yagni-finding-severity": check_yagni_finding_severity,
    "yagni-finding-ladder-step": check_yagni_finding_ladder_step,
    "yagni-findings-sorted": check_yagni_findings_sorted_by_ladder,
    "yagni-bootstrap-carveout": check_yagni_finding_carves_out_bootstrap,
    "yagni-no-above-medium": check_yagni_no_finding_above_medium,
}


def _dispatch(name: str, findings: list[dict]) -> tuple[bool, str]:
    """Dispatch a colon-separated check name to the right function."""
    parts = name.split(":", 2)
    fn_name = parts[0]
    fn = _BASE_CHECKS.get(fn_name)
    if fn is None:
        return False, f"unknown check: {fn_name}"

    if fn_name == "yagni-finding-present":
        if len(parts) < 2:
            return False, f"{fn_name} needs :<rule>"
        return fn(findings, parts[1])
    if fn_name == "yagni-finding-severity":
        if len(parts) < 3:
            return False, f"{fn_name} needs :<rule>:<severity>"
        return fn(findings, parts[1], parts[2])
    if fn_name == "yagni-finding-ladder-step":
        if len(parts) < 3:
            return False, f"{fn_name} needs :<rule>:<step>"
        try:
            step = int(parts[2])
        except ValueError:
            return False, f"{fn_name} step must be int, got {parts[2]!r}"
        return fn(findings, parts[1], step)
    if fn_name == "yagni-bootstrap-carveout":
        return fn(findings)
    if fn_name == "yagni-findings-sorted":
        return fn(findings)
    if fn_name == "yagni-no-above-medium":
        return fn(findings)
    return False, f"unhandled check: {fn_name}"


# ---------------------------------------------------------------------------
# run_checks — entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against an audit-output JSON file.

    Returns a skillgrade-style dict with ``score``, ``details``, and
    ``checks``.
    """
    findings, _raw = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        try:
            ok, msg = _dispatch(name, findings)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}
