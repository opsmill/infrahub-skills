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
        "severity": "MEDIUM",
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
    """Assert yagni-* findings are ordered by ladder_step, then by file path.

    The findings-sorted eval prompt requires ascending ladder_step
    (cheapest fix on top) and, within a step, ascending file path. Both
    keys are enforced here so a same-step pair emitted in the wrong file
    order is caught rather than scoring a passing 1.0.
    """
    yagni = [
        f for f in findings
        if isinstance(f, dict) and str(f.get("rule", "")).startswith("yagni-")
    ]
    if not yagni:
        return False, "no yagni-* findings emitted"
    pairs = [(f.get("ladder_step", -1), str(f.get("file", ""))) for f in yagni]
    if pairs != sorted(pairs):
        return False, f"yagni findings out of (ladder_step, file) order: {pairs}"
    return True, f"yagni findings sorted by (ladder_step, file): {pairs}"


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
    yagni = [
        f for f in findings
        if isinstance(f, dict) and str(f.get("rule", "")).startswith("yagni-")
    ]
    missing = [f for f in yagni if not str(f.get("severity", "")).strip()]
    above = [
        f for f in yagni
        if str(f.get("severity", "")).strip()
        and str(f.get("severity", "")).upper() not in ALLOWED
    ]
    if missing or above:
        msgs = []
        if above:
            msgs.append(
                "severity cap violated (MEDIUM max): "
                + str([f"{f.get('rule')}={f.get('severity')}" for f in above])
            )
        if missing:
            msgs.append(
                "missing severity field: "
                + str([f.get("rule") for f in missing])
            )
        return False, "; ".join(msgs)
    return True, "all yagni findings at MEDIUM or below"


# The generator-hardcoding rule (and Phase 9.4) carve out bootstrap,
# seed, AND demo paths — a substring match on any of these covers the
# `bootstrap/`, `seed/`, `demo/` directories and the `*_bootstrap.py` /
# `*_demo_data.py` file-name conventions the rule documents.
_BOOTSTRAP_CARVEOUT_SUBSTRINGS = ("bootstrap", "seed", "demo")


def check_yagni_finding_carves_out_bootstrap(
    findings: list[dict],
    carveout_substrings: tuple[str, ...] = _BOOTSTRAP_CARVEOUT_SUBSTRINGS,
) -> tuple[bool, str]:
    """Assert no yagni-generator-hardcoding-data finding fires on a carved-out path.

    Covers bootstrap/seed/demo, matching the rule's documented carve-out
    rather than only the literal ``bootstrap`` substring.
    """
    offenders = [
        f for f in findings
        if isinstance(f, dict)
        and f.get("rule") == "yagni-generator-hardcoding-data"
        and any(s in str(f.get("file", "")) for s in carveout_substrings)
    ]
    if offenders:
        return False, f"bootstrap/seed/demo carve-out violated on: {[f.get('file') for f in offenders]}"
    return True, "bootstrap/seed/demo carve-out respected"


def check_yagni_finding_file(
    findings: list[dict], rule: str, substring: str
) -> tuple[bool, str]:
    """Assert the named rule's finding is attributed to the expected file.

    Multi-artifact tasks have a production file that must be flagged and an
    exempt file that must not; presence/severity checks alone pass even when
    the finding points at the wrong file. This pins the attribution.
    """
    f = _find(findings, rule)
    if f is None:
        return False, f"{rule} missing — cannot check file"
    fpath = str(f.get("file", ""))
    if substring in fpath:
        return True, f"{rule} file={fpath}"
    return False, f"{rule} file={fpath!r} does not contain {substring!r}"


def check_yagni_no_finding_on_file(
    findings: list[dict], substring: str
) -> tuple[bool, str]:
    """Assert no finding is attributed to a file matching ``substring``.

    Generalises the bootstrap carve-out to any exempt file (e.g. the
    deterministic-derivation generator that must not be flagged).
    """
    offenders = [
        f for f in findings
        if isinstance(f, dict) and substring in str(f.get("file", ""))
    ]
    if offenders:
        return False, f"finding(s) on excluded file {substring!r}: {[f.get('rule') for f in offenders]}"
    return True, f"no finding on files matching {substring!r}"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------
#
# Keys use a colon-separated form to encode the rule (and any expected
# value) the check is being parameterised with, e.g.
# ``yagni-finding-severity:<rule>:<sev>``. Each registry entry carries its
# function and the parameter types (``"str"`` / ``"int"``) to parse from the
# colon parts, so ``_dispatch`` is fully data-driven — adding a check means
# adding one registry line, not a new branch in a hand-written if-chain.

_CHECKS: dict[str, tuple[Any, list[str]]] = {
    "yagni-finding-present": (check_yagni_finding_present, ["str"]),
    "yagni-finding-severity": (check_yagni_finding_severity, ["str", "str"]),
    "yagni-finding-ladder-step": (check_yagni_finding_ladder_step, ["str", "int"]),
    "yagni-finding-file": (check_yagni_finding_file, ["str", "str"]),
    "yagni-finding-file-excludes": (check_yagni_no_finding_on_file, ["str"]),
    "yagni-findings-sorted": (check_yagni_findings_sorted_by_ladder, []),
    "yagni-bootstrap-carveout": (check_yagni_finding_carves_out_bootstrap, []),
    "yagni-no-above-medium": (check_yagni_no_finding_above_medium, []),
}


def _dispatch(name: str, findings: list[dict]) -> tuple[bool, str]:
    """Dispatch a colon-encoded check name to its function.

    The name is ``<check>[:<arg>...]``; args are parsed positionally per the
    registry's param spec and passed to the function after ``findings``.
    """
    parts = name.split(":", len(name))  # split fully; values carry no colons
    fn_name = parts[0]
    raw_args = parts[1:]
    entry = _CHECKS.get(fn_name)
    if entry is None:
        return False, f"unknown check: {fn_name}"
    fn, specs = entry
    if len(raw_args) != len(specs):
        return False, f"{fn_name} expects {len(specs)} arg(s), got {len(raw_args)}: {raw_args}"
    parsed: list[Any] = []
    for spec, value in zip(specs, raw_args):
        if spec == "int":
            try:
                parsed.append(int(value))
            except ValueError:
                return False, f"{fn_name} arg must be int, got {value!r}"
        else:
            parsed.append(value)
    return fn(findings, *parsed)


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
