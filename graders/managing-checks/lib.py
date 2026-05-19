"""Shared grader library for infrahub-managing-checks skill evaluations.

The managing-checks skill produces three artifacts: a `.gql` query, a
Python class, and a `.infrahub.yml` registration. The eval prompt asks
the model to save a single combined `output.yml` representing the
`.infrahub.yml` content; assertions focus on the registration shape,
since that is where the most common confusion (the rejected `query:`
field on `check_definitions`) lives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# Allowed fields per InfrahubCheckDefinitionConfig (Pydantic extra="forbid")
# ---------------------------------------------------------------------------

ALLOWED_CHECK_DEF_FIELDS: set[str] = {
    "name",
    "file_path",
    "class_name",
    "targets",
    "parameters",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output(path: Path) -> tuple[dict, str]:
    """Load a YAML file and return (parsed_dict, raw_text)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}, ""
    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        parsed = {}
    return parsed, raw


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def check_check_definitions_present(config: dict, **_: Any) -> tuple[bool, str]:
    """`.infrahub.yml` declares at least one entry under check_definitions."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    names = [d.get("name", "?") for d in defs]
    return True, f"check_definitions: {', '.join(names)}"


def check_no_query_field_in_check_def(config: dict, **_: Any) -> tuple[bool, str]:
    """No entry under check_definitions contains a `query:` key.

    `InfrahubCheckDefinitionConfig` uses Pydantic `extra="forbid"`, so
    `query:` here causes the repository config to fail to load. The
    query is bound on the Python class via the `query = "..."`
    attribute, which references a name under top-level `queries:`.
    """
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        if "query" in entry:
            bad.append(entry.get("name", "?"))
    if bad:
        return False, f"Forbidden `query:` field on check_definitions[]: {', '.join(bad)}"
    return True, "No `query:` field on any check_definitions entry"


def check_only_allowed_fields_in_check_def(config: dict, **_: Any) -> tuple[bool, str]:
    """Each check_definitions entry uses only allowed fields."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        unknown = set(entry.keys()) - ALLOWED_CHECK_DEF_FIELDS
        if unknown:
            name = entry.get("name", "?")
            bad.append(f"{name}: {', '.join(sorted(unknown))}")
    if bad:
        return False, f"Unknown fields under check_definitions: {'; '.join(bad)}"
    return True, "All check_definitions entries use only allowed fields"


def check_queries_section_present(config: dict, **_: Any) -> tuple[bool, str]:
    """Top-level queries: section declares at least one query.

    The query that backs each check must be registered here; the Python
    class's `query = "..."` references this name.
    """
    queries = config.get("queries") or []
    if not queries:
        return False, "No top-level `queries:` entries found"
    names = [q.get("name", "?") for q in queries if isinstance(q, dict)]
    return True, f"queries: {', '.join(names)}"


def check_check_def_required_fields(config: dict, **_: Any) -> tuple[bool, str]:
    """Each check_definitions entry has the required fields name + file_path."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        missing = []
        if not name:
            missing.append("name")
        if not entry.get("file_path"):
            missing.append("file_path")
        if missing:
            bad.append(f"{name or '<unnamed>'}: {', '.join(missing)}")
    if bad:
        return False, f"check_definitions missing required fields: {'; '.join(bad)}"
    return True, "All check_definitions entries have name and file_path"


def check_targeted_has_targets_and_parameters(
    config: dict, **_: Any
) -> tuple[bool, str]:
    """When a check is described as targeted, it declares targets and parameters."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    found_targeted = False
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        if "targets" in entry:
            found_targeted = True
            name = entry.get("name", "?")
            if not entry.get("parameters"):
                bad.append(f"{name}: missing parameters")
    if not found_targeted:
        return False, "No targeted check_definitions entry found"
    if bad:
        return False, "; ".join(bad)
    return True, "All targeted check_definitions entries declare parameters"


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "check-definitions-present": check_check_definitions_present,
    "no-query-field-in-check-def": check_no_query_field_in_check_def,
    "only-allowed-fields-in-check-def": check_only_allowed_fields_in_check_def,
    "queries-section-present": check_queries_section_present,
    "check-def-required-fields": check_check_def_required_fields,
    "targeted-has-targets-and-parameters": check_targeted_has_targets_and_parameters,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point
# ---------------------------------------------------------------------------


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against an .infrahub.yml output and return skillgrade JSON."""
    config, _ = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(config)
        except Exception as exc:  # pragma: no cover
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
