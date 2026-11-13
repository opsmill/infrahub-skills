"""Shared grader library for the harvesting-release-notes contributor skill.

The model is prompted to read release notes for a range of Infrahub
releases, check each change against the skills in the workspace, and write
``REPORT.md``. The report has one ``### Finding <n>`` section per change that
touches a skill passage, each carrying these fields as list items::

    - Repository: opsmill/infrahub
    - Severity: High
    - Affected: skills/<skill>/rules/<file>.md:<line>
    - Deprecated in: infrahub-v1.6.0 | none
    - Removed in: infrahub-v1.7.0
    - Verified in: infrahub-v1.7.0:backend/infrahub/<path> | UNVERIFIED
    - Gate: <recommended version-gated text>

Every check parses that structure: finding sections, named fields, and the
versions inside them. None of them substring-matches the report as a whole.
See ``dev/guidelines/graders.md``.

Each check returns ``(bool, str)`` and takes ``text`` (the report) plus
``root`` (the workspace directory) and its own keyword arguments.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

REPORT_FILE = "REPORT.md"

FIELDS = (
    "repository",
    "severity",
    "affected",
    "deprecated in",
    "removed in",
    "verified in",
    "gate",
)
VALID_SEVERITY = {"critical", "high", "medium"}

_FINDING_RE = re.compile(r"^#{2,4}\s+Finding\b.*$", re.IGNORECASE | re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,4}\s+\S", re.MULTILINE)
_FIELD_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*|__)?(?P<key>[A-Za-z][A-Za-z ]*?)(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*(?P<value>.*)$"
)
# A version: 1.7, 1.7.0, v1.7.0, infrahub-v1.7.0, 1.7.0b1. The pre-release
# suffix is captured so a beta tag can be told apart from the final release.
_VERSION_RE = re.compile(
    r"(?<![\w.])(?:infrahub-)?v?(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?(?P<pre>(?:a|b|rc)\d+)?(?![\w])"
)
_SHA_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])")
# A path: at least one slash and a file extension.
_PATH_RE = re.compile(r"[\w.-]+(?:/[\w.-]+)+\.\w+")
_AFFECTED_RE = re.compile(r"(?P<path>[\w./-]+\.\w+):(?P<line>\d+)(?:-\d+)?")
# "Before 1.7" excludes 1.7 itself: the qualifier for the removal release.
_BEFORE_WORDS = re.compile(r"\b(before|prior to|pre|until|below)\b|<(?!=)", re.IGNORECASE)
# "1.6 and earlier" includes 1.6: the qualifier for the last release where the
# old guidance still works.
_INCLUSIVE_WORDS = re.compile(
    r"\b(and|or) (earlier|older|below)\b|\b(up to|through)\b|<=", re.IGNORECASE
)
_NONE_VALUES = {"", "none", "n/a", "-", "no recommendation"}


def _clean(value: str) -> str:
    """A field value with `*` emphasis and code ticks stripped. Underscores
    stay: they are part of filter names such as `name__like`."""
    return re.sub(r"[`*]", "", value).strip()


def _sections(text: str) -> list[str]:
    """Each finding section's body, from its heading to the next heading."""
    bodies = []
    for match in _FINDING_RE.finditer(text):
        start = match.end()
        nxt = _HEADING_RE.search(text, start)
        bodies.append(text[start : nxt.start() if nxt else len(text)])
    return bodies


def _fields(body: str) -> dict[str, str]:
    """The known fields of one finding. A value runs on to the following
    lines, so a multi-line gate is kept whole, and ends at the next known
    field or the first blank line: prose after the list is not a field."""
    out: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        m = _FIELD_RE.match(line)
        key = m.group("key").strip().lower() if m else None
        if key in FIELDS:
            current = key
            out[key] = m.group("value").strip()
        elif not line.strip():
            current = None
        elif current is not None and not line.strip().startswith("```"):
            out[current] = f"{out[current]}\n{line.strip()}"
    return out


def _findings(text: str) -> list[dict[str, str]]:
    return [_fields(body) for body in _sections(text)]


def _versions(text: str) -> list[tuple[int, int, int | None, str | None]]:
    out = []
    for m in _VERSION_RE.finditer(text):
        patch = m.group("patch")
        out.append(
            (int(m.group("major")), int(m.group("minor")), int(patch) if patch else None, m.group("pre"))
        )
    return out


def _minor(spec: str) -> tuple[int, int]:
    major, minor = spec.split(".")[:2]
    return int(major), int(minor)


def _full(spec: str) -> tuple[int, int, int]:
    parts = [int(p) for p in spec.split(".")]
    return tuple((parts + [0, 0, 0])[:3])  # type: ignore[return-value]


def _is_unverified(finding: dict[str, str]) -> bool:
    return _clean(finding.get("verified in", "")).upper().startswith("UNVERIFIED")


def _affected_paths(value: str) -> list[tuple[str, str]]:
    return [(m.group("path"), m.group("line")) for m in _AFFECTED_RE.finditer(_clean(value))]


def _target(text: str, affected_path: str) -> dict[str, str] | None:
    """The finding whose Affected field names the given skill file."""
    for finding in _findings(text):
        for path, _line in _affected_paths(finding.get("affected", "")):
            if path == affected_path or path.endswith("/" + affected_path):
                return finding
    return None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_report_has_findings(text: str, **_) -> tuple[bool, str]:
    """The report has at least one finding section."""
    if not text.strip():
        return False, f"No {REPORT_FILE} was written"
    if not _sections(text):
        return False, "The report has no '### Finding' section"
    return True, f"{len(_sections(text))} finding section(s)"


def check_finding_fields_present(text: str, **_) -> tuple[bool, str]:
    """Every finding carries every field, with a valid severity and a
    file:line location. An UNVERIFIED finding may leave Gate empty."""
    findings = _findings(text)
    if not findings:
        return False, "No findings to check"
    for i, finding in enumerate(findings, start=1):
        unverified = _is_unverified(finding)
        for field in FIELDS:
            if field == "gate" and unverified:
                continue
            if not _clean(finding.get(field, "")):
                return False, f"Finding {i} has no '{field}' field"
        severity = _clean(finding["severity"]).split()[0].lower()
        if severity not in VALID_SEVERITY:
            return False, f"Finding {i} severity '{severity}' is not one of {sorted(VALID_SEVERITY)}"
        if not _affected_paths(finding["affected"]):
            return False, f"Finding {i} Affected '{_clean(finding['affected'])}' has no file:line"
    return True, f"All {len(findings)} finding(s) carry every field"


def check_affected_paths_exist(text: str, root: Path, **_) -> tuple[bool, str]:
    """Every passage a finding names exists in the workspace, at a line the
    file has. A change that touches no passage is not a finding, so a finding
    for one has to name a file or a line that is not there."""
    findings = _findings(text)
    if not findings:
        return False, "No findings to check"
    for i, finding in enumerate(findings, start=1):
        for path, line in _affected_paths(finding.get("affected", "")):
            target = root / path
            if not target.is_file():
                return False, f"Finding {i} names {path}, which does not exist"
            if int(line) > len(target.read_text(errors="ignore").splitlines()):
                return False, f"Finding {i}: {path}:{line} is past the end of the file"
    return True, "Every affected passage exists"


def check_target_finding_present(text: str, affected_path: str, **_) -> tuple[bool, str]:
    """A finding points at the skill passage the release changed."""
    if _target(text, affected_path) is None:
        return False, f"No finding names {affected_path}:<line> in Affected"
    return True, f"A finding names {affected_path}"


def check_evidence_pinned(text: str, start: str, end: str, **_) -> tuple[bool, str]:
    """Every finding is either declared UNVERIFIED with no recommendation, or
    names a source path at a pinned version: a final release inside the range,
    or a commit SHA. No finding cites a pre-release."""
    findings = _findings(text)
    if not findings:
        return False, "No findings to check"
    lo, hi = _full(start), _full(end)
    for i, finding in enumerate(findings, start=1):
        # Every field, not only the version fields: a beta named in the gate
        # is cited just the same.
        for field in FIELDS:
            for v in _versions(_clean(finding.get(field, ""))):
                if v[3]:
                    return False, f"Finding {i} '{field}' cites a pre-release ({v[0]}.{v[1]}.{v[2]}{v[3]})"
        if _is_unverified(finding):
            gate = _clean(finding.get("gate", "")).lower()
            if gate not in _NONE_VALUES:
                return False, f"Finding {i} is UNVERIFIED but still recommends a gate"
            continue
        value = _clean(finding.get("verified in", ""))
        if not _PATH_RE.search(value):
            return False, f"Finding {i} 'Verified in' names no source path: '{value}'"
        pinned = bool(_SHA_RE.search(value))
        for v in _versions(value):
            if v[2] is not None and lo <= (v[0], v[1], v[2]) <= hi:
                pinned = True
        if not pinned:
            return False, (
                f"Finding {i} 'Verified in' is not pinned to a release in {start}..{end} "
                f"or a commit: '{value}'"
            )
    return True, "Every finding's evidence is pinned or declared UNVERIFIED"


def check_gate_boundaries(
    text: str, affected_path: str, deprecated: str | None, removed: str, **_
) -> tuple[bool, str]:
    """The finding's Deprecated in and Removed in fields, and the versions its
    Gate names, match the releases where the change was deprecated and where
    the old guidance stopped working. With no deprecation release, the gate
    names the removal release alone."""
    finding = _target(text, affected_path)
    if finding is None:
        return False, f"No finding names {affected_path}"
    want = {_minor(removed)} | ({_minor(deprecated)} if deprecated else set())

    dep_field = _clean(finding.get("deprecated in", ""))
    dep_seen = {(v[0], v[1]) for v in _versions(dep_field)}
    if deprecated and dep_seen != {_minor(deprecated)}:
        return False, f"'Deprecated in' is '{dep_field}', expected {deprecated}"
    if not deprecated and dep_seen:
        return False, f"'Deprecated in' is '{dep_field}', expected none"
    rem_field = _clean(finding.get("removed in", ""))
    if {(v[0], v[1]) for v in _versions(rem_field)} != {_minor(removed)}:
        return False, f"'Removed in' is '{rem_field}', expected {removed}"

    gate = _clean(finding.get("gate", ""))
    seen = {(v[0], v[1]) for v in _versions(gate)}
    if seen != want:
        names = ", ".join(f"{a}.{b}" for a, b in sorted(seen)) or "no version"
        expect = ", ".join(f"{a}.{b}" for a, b in sorted(want))
        return False, f"Gate names {names}; expected exactly {expect}"
    return True, "Gate names the deprecation and removal releases"


def _clauses(gate: str) -> list[str]:
    parts = re.split(r"\n|;|(?<=[.!?])\s+(?=[A-Z(`*])", gate)
    return [p.strip() for p in parts if p.strip()]


def check_gate_keeps_old_guidance(
    text: str,
    affected_path: str,
    old_token: str,
    removed: str,
    deprecated: str | None = None,
    new_token: str | None = None,
    **_,
) -> tuple[bool, str]:
    """The Gate leaves no release without working guidance.

    The new behavior is available from the deprecation release (or from the
    removal release when there was none). The old guidance must reach that
    release: one clause names the old token with 'before <v>' or '<v> and
    earlier', where v lies between the availability release and the removal
    release. With a deprecation release, a clause naming the new token must
    also name the availability release, so the new guidance starts where the
    old one stops. 'From 1.7: new. Before 1.6: old.' leaves 1.6 uncovered.
    """
    finding = _target(text, affected_path)
    if finding is None:
        return False, f"No finding names {affected_path}"
    rem = _minor(removed)
    avail = _minor(deprecated) if deprecated else rem
    clauses = _clauses(_clean(finding.get("gate", "")))
    old_reaches = False
    for clause in clauses:
        if old_token not in clause:
            continue
        versions = {(v[0], v[1]) for v in _versions(clause)}
        if any(avail <= v <= rem for v in versions) and _BEFORE_WORDS.search(clause):
            old_reaches = True
        if any(avail <= v < rem for v in versions) and _INCLUSIVE_WORDS.search(clause):
            old_reaches = True
    if not old_reaches:
        return False, (
            f"No Gate clause keeps '{old_token}' up to {avail[0]}.{avail[1]}, "
            f"where the new behavior became available"
        )
    if deprecated and new_token:
        starts = any(
            new_token in clause and avail in {(v[0], v[1]) for v in _versions(clause)}
            for clause in clauses
        )
        if not starts:
            return False, f"No Gate clause starts '{new_token}' at {deprecated}, so a release has no guidance"
    return True, f"Gate covers every release: '{old_token}' up to {avail[0]}.{avail[1]}, then '{new_token or 'the new behavior'}'"


def check_severity(text: str, affected_path: str, expected: str, **_) -> tuple[bool, str]:
    """The finding's severity matches the consequence-ranked scale."""
    finding = _target(text, affected_path)
    if finding is None:
        return False, f"No finding names {affected_path}"
    words = _clean(finding.get("severity", "")).split()
    got = words[0].lower() if words else ""
    if got != expected:
        return False, f"Severity is '{got}', expected '{expected}'"
    return True, f"Severity is {expected}"


def check_skill_unchanged(text: str, root: Path, files: dict[str, str], **_) -> tuple[bool, str]:
    """The skill files in the workspace are byte-identical to the fixture:
    the harvester reports, it does not edit."""
    for rel, digest in files.items():
        path = root / rel
        if not path.exists():
            return False, f"{rel} was deleted"
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False, f"{rel} was edited; the harvester only reports"
    return True, "Skill files untouched"


CHECKS = {
    "report-has-findings": check_report_has_findings,
    "finding-fields-present": check_finding_fields_present,
    "affected-paths-exist": check_affected_paths_exist,
    "target-finding-present": check_target_finding_present,
    "evidence-pinned": check_evidence_pinned,
    "gate-boundaries": check_gate_boundaries,
    "gate-keeps-old-guidance": check_gate_keeps_old_guidance,
    "severity": check_severity,
    "skill-unchanged": check_skill_unchanged,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the report; return skillgrade JSON."""
    text = output_path.read_text(errors="ignore") if output_path.exists() else ""
    root = output_path.resolve().parent
    entries: list[dict] = []
    passed_count = 0
    for spec in check_specs:
        name, kwargs = spec if isinstance(spec, tuple) else (spec, {})
        fn = CHECKS.get(name)
        if fn is None:
            entries.append({"name": name, "passed": False, "message": f"Unknown check: {name}"})
            continue
        try:
            ok, msg = fn(text, root=root, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})
    total = len(check_specs)
    score = round(passed_count / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}
