"""Shared grader library for infrahub-managing-checks skill evaluations.

The managing-checks skill produces three artifacts: a `.gql` query, a
Python class, and a `.infrahub.yml` registration. The eval prompt asks
the model to save a single combined `output.yml` representing the
`.infrahub.yml` content; assertions focus on the registration shape,
since that is where the most common confusion (the rejected `query:`
field on `check_definitions`) lives.
"""

from __future__ import annotations

import re
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


# ---------------------------------------------------------------------------
# Text-based checks
# ---------------------------------------------------------------------------
#
# Some rules grade the produced artifacts (a `.gql` query and a Python check
# class), not the `.infrahub.yml` registration. Those checks take the raw
# file text rather than a parsed config, so they live in TEXT_CHECKS and run
# through run_text_checks. Each has the same (bool, str) contract as the
# config checks above.


def _last_node_block(gql: str) -> str | None:
    """Return the balanced `{...}` body of the last `node {` in the query.

    The innermost `node {` is the related node reached by traversal; its
    selection set is where the comparison attribute must appear. Returns
    None when there is no relationship traversal (fewer than two `node {`).
    """
    matches = list(re.finditer(r"node\s*{", gql))
    if len(matches) < 2:
        return None
    start = matches[-1].end() - 1  # index of the opening brace
    depth = 0
    for i in range(start, len(gql)):
        ch = gql[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return gql[start + 1 : i]
    return gql[start + 1 :]  # unbalanced; grade against the remainder


def _none_guard_blocks(py: str) -> list[str]:
    """Return the body of each `if <parent> is None:` / `if not <parent>:` block.

    Restricted to None / empty-truthiness guards so a `status not in ALLOWED`
    comparison is not mistaken for an unresolvable-parent guard.
    """
    lines = py.split("\n")
    is_none = re.compile(r"^(\s*)if\s+.+\bis\s+None\s*:\s*$")
    is_falsy = re.compile(r"^(\s*)if\s+not\s+[\w.\(\)\[\]\"']+\s*:\s*$")
    blocks: list[str] = []
    for i, line in enumerate(lines):
        m = is_none.match(line) or is_falsy.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        body: list[str] = []
        for nxt in lines[i + 1 :]:
            if not nxt.strip():
                continue
            if len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        blocks.append("\n".join(body))
    return blocks


def text_child_status_filter(gql: str, py: str) -> tuple[bool, str]:
    """The query filters the child set by an attribute value (e.g. status__value:)."""
    if re.search(r"\w+__value\s*:", gql):
        return True, "Query filters children by an attribute value"
    return False, "Query has no `<attr>__value:` filter selecting the constrained children"


def text_traverses_related_node(gql: str, py: str) -> tuple[bool, str]:
    """The query nests into a related node (>= 2 `node {` blocks)."""
    opens = len(re.findall(r"node\s*{", gql))
    if opens >= 2:
        return True, f"Query traverses into a related node ({opens} `node {{` blocks)"
    return False, "Query does not traverse a relationship into a nested `node {` block"


def text_fetches_related_attribute_value(gql: str, py: str) -> tuple[bool, str]:
    """The comparison attribute is selected inside the innermost related node.

    Guards finding 1: selecting the child's own `name { value }` after the
    nested block must not satisfy this — the value has to sit in the related
    node's own selection set.
    """
    block = _last_node_block(gql)
    if block is None:
        return False, "No nested related node to hold the comparison attribute"
    if re.search(r"\bvalue\b", block):
        return True, "Innermost related node selects an attribute value (parent state is fetched)"
    return False, "Innermost related node selects no attribute `value`; parent state is not fetched"


def text_uses_infrahubcheck(gql: str, py: str) -> tuple[bool, str]:
    """Python defines an InfrahubCheck subclass bound to a query."""
    if "InfrahubCheck" in py and re.search(r"query\s*=", py):
        return True, "Defines an InfrahubCheck with a `query =` binding"
    return False, "No InfrahubCheck subclass with a `query =` attribute"


def text_surfaces_violation(gql: str, py: str) -> tuple[bool, str]:
    """validate() surfaces a mismatch via log_error (blocks the merge)."""
    if re.search(r"log_error\s*\(", py):
        return True, "Reports a violation with log_error"
    return False, "validate() never calls log_error, so no violation is surfaced"


def text_null_safe_traversal(gql: str, py: str) -> tuple[bool, str]:
    """Each relationship hop is guarded against null (`or {}` / `.get(k, {})`)."""
    if "or {}" in py or re.search(r"\.get\([^)]*,\s*{}\)", py):
        return True, "Guards each relationship hop against null (`or {}` / `.get(k, {})`)"
    return False, "No per-hop null guard (`or {}` / `.get(k, {})`) on the relationship walk"


def text_flags_unresolvable_parent(gql: str, py: str) -> tuple[bool, str]:
    """An unresolvable related node is flagged, not silently skipped.

    Guards finding 2: `if parent is None: continue` (a skip) must fail; the
    branch has to call log_error. Absence of any such guard also fails,
    since the rule requires handling the unresolvable case explicitly.
    """
    blocks = _none_guard_blocks(py)
    if not blocks:
        return False, "No guard for an unresolvable related node (the rule requires flagging it)"
    if any("log_error" in b for b in blocks):
        return True, "Flags an unresolvable related node with log_error instead of skipping"
    return False, "The unresolvable-parent branch skips (continue/return) without log_error"


TEXT_CHECKS: dict[str, Any] = {
    "child-status-filter": text_child_status_filter,
    "traverses-related-node": text_traverses_related_node,
    "fetches-related-attribute-value": text_fetches_related_attribute_value,
    "uses-infrahubcheck": text_uses_infrahubcheck,
    "surfaces-violation": text_surfaces_violation,
    "null-safe-traversal": text_null_safe_traversal,
    "flags-unresolvable-parent": text_flags_unresolvable_parent,
}


def run_text_checks(check_names: list[str], sources: dict[str, str]) -> dict:
    """Run named TEXT_CHECKS against produced source files and return skillgrade JSON.

    `sources` maps a label (e.g. "gql", "py") to that file's raw text.
    """
    gql = sources.get("gql", "")
    py = sources.get("py", "")

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = TEXT_CHECKS[name]
        try:
            ok, msg = fn(gql, py)
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
