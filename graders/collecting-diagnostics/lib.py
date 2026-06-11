"""Shared grader library for infrahub-collecting-diagnostics skill evaluations.

The skill produces a *bundle directory* rather than a single output file, so
checks here inspect the directory tree, the ``manifest.yml``, ``flags.yml``,
``redaction-report.txt``, and individual log/config files.

Each check function takes ``(bundle_path, **kwargs)`` and returns
``(passed: bool, message: str)``. The ``CHECKS`` registry maps assertion names
to check functions. Some checks accept kwargs (e.g., ``flag-fired`` needs a
``flag_id``); pass them via ``run_checks`` task tuples.

Usage (per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        [
            "bundle-root",
            "baseline-present",
            "no-unredacted-secrets",
            ("manifest-category", {"category": "git-sync"}),
            ("flag-fired", {"flag_id": "commit-not-found"}),
        ],
        Path("output_bundle"),
    )
    print(result)  # {"score": ..., "details": "...", "checks": [...]}

Return shape matches the sibling ``graders/managing-menus/lib.py`` so
skillgrade ingests it identically.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


CheckResult = tuple[bool, str]
CheckFn = Callable[..., CheckResult]


# ---------------------------------------------------------------------------
# Low-level bundle helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> Any:
    """Load YAML from path; return None if file is missing."""
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


def _iter_text_files(bundle: Path):
    """Yield text files in the bundle, skipping binaries and known archives."""
    binary_suffixes = {
        ".bin", ".tar", ".tgz", ".gz", ".zip", ".png", ".jpg", ".jpeg",
        ".pdf", ".har", ".pyc", ".whl",
    }
    for path in bundle.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in binary_suffixes:
            continue
        yield path


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_bundle_root(bundle: Path, **_: object) -> CheckResult:
    """Bundle root contains manifest.yml and README.md."""
    if not bundle.exists() or not bundle.is_dir():
        return False, f"Bundle path '{bundle}' is not a directory"
    missing = [
        name for name in ("manifest.yml", "README.md")
        if not (bundle / name).exists()
    ]
    if missing:
        return False, f"Missing root files: {missing}"
    return True, "Bundle root has manifest.yml + README.md"


def check_baseline_present(bundle: Path, **_: object) -> CheckResult:
    """baseline/ contains the canonical files and a logs/ subdirectory."""
    required = ["versions.yml", "api-config.json", "deployment.yml", "host.yml"]
    base = bundle / "baseline"
    if not base.exists():
        return False, "baseline/ directory missing"
    missing = [name for name in required if not (base / name).exists()]
    if missing:
        return False, f"Missing baseline files: {missing}"
    log_dir = base / "logs"
    if not log_dir.is_dir():
        return False, "baseline/logs/ directory missing"
    if not any(log_dir.iterdir()):
        return False, "baseline/logs/ is empty"
    return True, "Baseline has required files and logs/"


_SECRET_PATTERNS = (
    # Env key=value style. Matches keys containing a sensitive word as a
    # substring, including underscore-bounded shapes like INFRAHUB_DB_PASSWORD.
    # Python's \b treats _ as a word char, so we can't rely on \b alone to find
    # _PASSWORD within INFRAHUB_DB_PASSWORD; instead we let [\w]* swallow the
    # surrounding env-key chars and anchor on a non-word char (or line start)
    # before the key.
    re.compile(
        r"(?im)"
        r"(?:^|[^\w])"  # boundary: line start or a non-word char (incl. quotes)
        r"\w*"
        r"(?:password|secret|token|client_secret|api_key|aws_secret_access_key|auth_token|bearer|private_key)"
        r"\w*"
        r"\s*[:=]\s*"
        r"['\"]?"
        # Skip already-redacted values and obvious non-secret literals
        # (booleans, null, small integers, enable/disable flags).
        r"(?!\*+REDACTED|true|false|null|none|yes|no|enabled|disabled|\d+[\s,'\"}\]]*$)"
        r"[^'\"\s#]{4,}"
    ),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\b"
    ),  # JWT — minimum {alg:HS256} header is ~18 chars including 'ey', so {10,} is safe
    re.compile(r"https?://[^\s/:@]+:[^\s/@]+@"),  # URL credentials
)


def check_no_unredacted_secrets(bundle: Path, **_: object) -> CheckResult:
    """No file in the bundle contains common secret shapes (allow REDACTED markers)."""
    offenders: list[str] = []
    for path in _iter_text_files(bundle):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for pattern in _SECRET_PATTERNS:
            m = pattern.search(text)
            if not m:
                continue
            window = text[max(0, m.start() - 30): m.end() + 30]
            if "REDACTED" in window or "redacted" in window:
                continue
            offenders.append(
                f"{path.relative_to(bundle)}: matched /{pattern.pattern[:60]}.../"
            )
            break  # one finding per file is enough
    if offenders:
        return False, f"Unredacted secrets: {offenders[:3]}"
    return True, "No unredacted secrets detected"


def check_multi_replica_logs(bundle: Path, **_: object) -> CheckResult:
    """If manifest claims worker_replicas > 1, each replica must have a log file."""
    manifest = _load_yaml(bundle / "manifest.yml") or {}
    replicas = manifest.get("deployment", {}).get("worker_replicas", 1)
    if not isinstance(replicas, int) or replicas <= 1:
        return True, f"worker_replicas={replicas}; single-replica skip"
    log_dir = bundle / "baseline" / "logs"
    if not log_dir.exists():
        return False, "baseline/logs/ missing — cannot verify replica coverage"
    worker_logs = [p for p in log_dir.glob("*task-worker*") if p.is_file()]
    if len(worker_logs) < replicas:
        return (
            False,
            f"manifest claims {replicas} workers, found {len(worker_logs)} log files",
        )
    return True, f"All {replicas} replica logs present"


def check_flags_yml_shape(bundle: Path, **_: object) -> CheckResult:
    """flags.yml is a YAML list; each entry has id/severity/evidence/hint."""
    path = bundle / "flags.yml"
    if not path.exists():
        return False, "flags.yml missing"
    flags = _load_yaml(path) or []
    if not isinstance(flags, list):
        return False, "flags.yml must be a YAML list at the root"
    required_keys = {"id", "severity", "evidence", "hint"}
    for i, entry in enumerate(flags):
        if not isinstance(entry, dict):
            return False, f"flags.yml[{i}] is not a mapping"
        missing = required_keys - set(entry.keys())
        if missing:
            return False, f"flags.yml[{i}] missing keys: {sorted(missing)}"
        if entry.get("severity") not in {"info", "warning"}:
            return False, f"flags.yml[{i}].severity must be info or warning"
    return True, f"flags.yml shape ok ({len(flags)} entries)"


def check_flag_fired(bundle: Path, *, flag_id: str = "", **_: object) -> CheckResult:
    """A specific flag id is present in flags.yml."""
    if not flag_id:
        return False, "check_flag_fired requires flag_id kwarg"
    flags = _load_yaml(bundle / "flags.yml") or []
    if not isinstance(flags, list):
        return False, "flags.yml is not a list"
    for entry in flags:
        if isinstance(entry, dict) and entry.get("id") == flag_id:
            return True, f"Flag '{flag_id}' fired"
    return False, f"Expected flag '{flag_id}' not found"


def check_manifest_category(
    bundle: Path, *, category: str = "", **_: object
) -> CheckResult:
    """manifest.yml problem.category equals the expected value."""
    if not category:
        return False, "check_manifest_category requires category kwarg"
    manifest = _load_yaml(bundle / "manifest.yml") or {}
    actual = manifest.get("problem", {}).get("category")
    if actual != category:
        return False, f"Expected problem.category='{category}', got '{actual}'"
    return True, f"problem.category='{category}' as expected"


def check_redaction_report_present(bundle: Path, **_: object) -> CheckResult:
    """redaction-report.txt exists and is non-empty."""
    path = bundle / "redaction-report.txt"
    if not path.exists():
        return False, "redaction-report.txt missing"
    text = path.read_text()
    if "REDACTED" not in text and "redacted" not in text:
        return False, "redaction-report.txt has no REDACTED markers"
    return True, "redaction-report.txt present"


def check_category_dir_present(
    bundle: Path, *, category: str = "", **_: object
) -> CheckResult:
    """category/<category>/ directory exists and is non-empty."""
    if not category:
        return False, "check_category_dir_present requires category kwarg"
    cat_dir = bundle / "category" / category
    if not cat_dir.exists() or not cat_dir.is_dir():
        return False, f"category/{category}/ missing"
    if not any(cat_dir.iterdir()):
        return False, f"category/{category}/ is empty"
    return True, f"category/{category}/ present and non-empty"


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------


CHECKS: dict[str, CheckFn] = {
    "bundle-root": check_bundle_root,
    "baseline-present": check_baseline_present,
    "no-unredacted-secrets": check_no_unredacted_secrets,
    "multi-replica-logs": check_multi_replica_logs,
    "flags-yml-shape": check_flags_yml_shape,
    "flag-fired": check_flag_fired,
    "manifest-category": check_manifest_category,
    "redaction-report-present": check_redaction_report_present,
    "category-dir-present": check_category_dir_present,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point
# ---------------------------------------------------------------------------


# A spec is either "check-name" (no kwargs) or ("check-name", {"k": "v"}).
CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], bundle: Path) -> dict:
    """Run named checks against a bundle directory; return skillgrade JSON.

    Returns
    -------
    dict with keys:
        - ``score`` (float 0.0-1.0)
        - ``details`` (str summary)
        - ``checks`` (list of ``{"name", "passed", "message"}``)
    """
    entries: list[dict] = []
    passed_count = 0

    for spec in check_specs:
        if isinstance(spec, tuple):
            name, kwargs = spec
        else:
            name, kwargs = spec, {}

        fn = CHECKS.get(name)
        if fn is None:
            entries.append(
                {"name": name, "passed": False, "message": f"Unknown check: {name}"}
            )
            continue

        try:
            ok, msg = fn(bundle, **kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"

        if ok:
            passed_count += 1
        # Disambiguate parameterized check names in the entry for clarity.
        display_name = name
        if kwargs:
            display_name = f"{name}({','.join(f'{k}={v}' for k, v in kwargs.items())})"
        entries.append({"name": display_name, "passed": ok, "message": msg})

    total = len(check_specs)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}


def main_cli() -> None:
    """Tiny CLI for ad-hoc verification: `python lib.py <bundle> <check>...`."""
    import sys

    if len(sys.argv) < 3:
        print(
            "usage: python lib.py <bundle-path> <check-name> [<check-name> ...]",
            file=sys.stderr,
        )
        raise SystemExit(2)
    bundle = Path(sys.argv[1])
    specs: list[CheckSpec] = list(sys.argv[2:])
    print(json.dumps(run_checks(specs, bundle), indent=2))


if __name__ == "__main__":
    main_cli()
