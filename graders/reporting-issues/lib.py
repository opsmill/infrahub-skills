"""Shared grader library for infrahub-reporting-issues skill evaluations.

The skill produces markdown issue bodies, not YAML. Checks here scan the
raw text for prohibited patterns (sanitization) and required structural
elements (title format, environment section).

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["no-leaked-ips", "no-internal-hostnames", "no-tokens"],
        Path("output.md"),
    )
    print(result)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Output loading
# ---------------------------------------------------------------------------


def load_output(path: Path) -> str:
    """Read the model's output file as text."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Sanitization check functions
# ---------------------------------------------------------------------------


# Allow-list of public IPs that may legitimately appear in docs/examples.
# Loopback and documentation-prefix ranges (RFC 5737) are not sensitive.
_PUBLIC_IP_ALLOWLIST = {
    "127.0.0.1",
    "0.0.0.0",
    "255.255.255.255",
}

# IPv4 regex — four octets 0-255. Loose; we filter false-positives below.
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)

# Documentation-prefix ranges per RFC 5737 — fine to leave in examples.
_DOC_IP_PREFIXES = ("192.0.2.", "198.51.100.", "203.0.113.")


def _is_allowed_ip(ip: str) -> bool:
    if ip in _PUBLIC_IP_ALLOWLIST:
        return True
    if ip.startswith(_DOC_IP_PREFIXES):
        return True
    # Placeholder check — sometimes models write <1.2.3.4>-style placeholders
    return False


def check_no_leaked_ips(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if the output contains real-looking IPv4 addresses."""
    found: list[str] = []
    for match in _IPV4_RE.finditer(text):
        ip = match.group(0)
        if _is_allowed_ip(ip):
            continue
        # Skip IPs inside placeholder markers like <internal-ip:10.0.0.1>
        start = max(0, match.start() - 20)
        end = min(len(text), match.end() + 20)
        window = text[start:end]
        if "<internal-ip>" in window or "<redacted>" in window:
            # Already adjacent to a placeholder — probably commentary
            continue
        found.append(ip)
    if found:
        sample = ", ".join(found[:3])
        return False, f"Leaked IPs detected: {sample}"
    return True, "No leaked IPs"


# Internal-looking TLDs and hostname suffixes. Models should redact these.
_INTERNAL_TLD_RE = re.compile(
    r"\b[a-z0-9][a-z0-9-]{0,62}"
    r"(?:\.[a-z0-9][a-z0-9-]{0,62})+"
    r"\.(?:local|internal|corp|lan|intranet|home|private)\b",
    re.IGNORECASE,
)


def check_no_internal_hostnames(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if hostnames with internal-looking TLDs are present."""
    matches = _INTERNAL_TLD_RE.findall(text)
    if matches:
        sample = ", ".join(matches[:3])
        return False, f"Internal hostnames detected: {sample}"
    return True, "No internal hostnames"


# Token patterns. Conservative — better to flag false-positives than miss real
# tokens. Models should redact and ask the user, not autocorrect.
_TOKEN_RES = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub tokens
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style secret keys
    re.compile(r"xox[bpoa]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key ID
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),  # JWT
]


def check_no_tokens(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if any common secret-token pattern is present."""
    for pattern in _TOKEN_RES:
        match = pattern.search(text)
        if match:
            return False, f"Token-like string detected: pattern {pattern.pattern[:20]}..."
    return True, "No tokens detected"


# Filesystem paths containing user home directories.
_USER_HOME_RE = re.compile(r"(?:/Users/|/home/|C:\\Users\\)[A-Za-z][\w.-]+")


def check_no_user_paths(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if filesystem paths containing usernames are present."""
    matches = _USER_HOME_RE.findall(text)
    # Filter examples that the model preserved inside placeholders or code
    # fences specifically demonstrating sanitization.
    real = [m for m in matches if not m.endswith("<user>") and not m.endswith("<name>")]
    if real:
        sample = ", ".join(real[:3])
        return False, f"User home paths detected: {sample}"
    return True, "No user home paths"


# ---------------------------------------------------------------------------
# Structural checks (light-touch — content not exhaustively validated)
# ---------------------------------------------------------------------------


def check_has_environment_section(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if the output has no Environment / Versions section."""
    if re.search(
        r"^#{1,3}\s*(environment|versions?|system info)\b",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        return True, "Environment section present"
    return False, "No Environment/Versions section found"


def check_has_title(text: str, **_: Any) -> tuple[bool, str]:
    """Fail if no plausible title line is present.

    A title is a first-level heading or a leading `Title:` line. Required
    so the user-review step has something to evaluate.
    """
    first_nonblank = next((line for line in text.splitlines() if line.strip()), "")
    if first_nonblank.startswith("#") or re.match(
        r"^title:\s*\S", first_nonblank, re.IGNORECASE
    ):
        return True, "Title line present"
    return False, "No title line found at top of output"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------


CHECKS = {
    "no-leaked-ips": check_no_leaked_ips,
    "no-internal-hostnames": check_no_internal_hostnames,
    "no-tokens": check_no_tokens,
    "no-user-paths": check_no_user_paths,
    "has-environment-section": check_has_environment_section,
    "has-title": check_has_title,
}


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against the output file and return skillgrade JSON."""
    text = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(text)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    if failed:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}


if __name__ == "__main__":  # pragma: no cover
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(list(CHECKS.keys()), out), indent=2))
