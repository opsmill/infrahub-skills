"""Shared grader library for infrahub-managing-checks skill evaluations.

The managing-checks skill produces three artifacts: a `.gql` query, a
Python class, and a `.infrahub.yml` registration. The eval prompt asks
the model to save a single combined `output.yml` representing the
`.infrahub.yml` content; assertions focus on the registration shape,
since that is where the most common confusion (the rejected `query:`
field on `check_definitions`) lives.
"""

from __future__ import annotations

import ast
import re
import textwrap
import ast
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


def load_output_py(path: Path) -> tuple[ast.Module | None, str]:
    """Load a Python check file and return ``(parsed_tree, raw_text)``.

    ``(None, "")`` when absent, ``(None, raw)`` on a syntax error, so the
    checks below can distinguish "no file" from "unparseable file".
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None, ""
    try:
        return ast.parse(raw), raw
    except SyntaxError:
        return None, raw


# ---------------------------------------------------------------------------
# Error-surface checks
#
# The server hard-codes status_code=200 on every executed GraphQL request and
# puts rejections in the body's `errors` array, so branching on the status
# code fails OPEN: the check passes on the case it exists to catch. The SDK's
# execute_graphql already raises GraphQLError when `"errors" in response`, so
# the fix is to use it. Verified against Infrahub 1.11.0 / SDK 1.23.1.
# ---------------------------------------------------------------------------

_RAW_HTTP_MARKERS = ("httpx.", "requests.", "urllib.request", "aiohttp.")


def check_uses_sdk_execute_graphql(
    _config: dict | None = None, *, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """Follow-up calls must go through the SDK client, which raises on errors."""
    if not py_raw:
        return False, "no Python source found"
    if "execute_graphql" not in py_raw:
        return False, "does not call self.client.execute_graphql"
    raw_http = [m for m in _RAW_HTTP_MARKERS if m in py_raw]
    if raw_http:
        return False, f"uses raw HTTP ({sorted(raw_http)}) instead of the SDK client"
    return True, "uses self.client.execute_graphql"


def check_no_status_code_branch(
    _config: dict | None = None, *, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """Branching on an HTTP status code to detect a rejection fails open."""
    if not py_raw:
        return False, "no Python source found"
    if re.search(r"status_code", py_raw):
        return False, (
            "branches on status_code; every executed GraphQL request returns "
            "200 even when the body carries errors"
        )
    return True, "does not branch on a status code"


def check_catches_graphql_error(
    _config: dict | None = None, *, tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """A rejection must be handled as a raised GraphQLError, and logged as an error."""
    if tree is None:
        return False, "check file missing or has a syntax error"
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    if not handlers:
        return False, "no except handler; a rejection raises GraphQLError"

    names: list[str] = []
    for handler in handlers:
        node = handler.type
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.Tuple):
            names.extend(
                e.id if isinstance(e, ast.Name) else getattr(e, "attr", "?")
                for e in node.elts
            )
        elif node is None:
            names.append("bare except")

    if "GraphQLError" not in names:
        return False, f"catches {names} but not GraphQLError"
    if "Exception" in names or "bare except" in names:
        return False, (
            f"catches {names}; a broad handler around execute_graphql "
            "reintroduces fail-open"
        )
    if "log_error" not in py_raw:
        return False, "catches GraphQLError but never calls log_error, so the check still passes"
    return True, "catches GraphQLError and logs an error"


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
    "uses-sdk-execute-graphql": check_uses_sdk_execute_graphql,
    "no-status-code-branch": check_no_status_code_branch,
    "catches-graphql-error": check_catches_graphql_error,
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


def run_checks(
    check_names: list[str],
    output_path: Path,
    py_path: Path | None = None,
) -> dict:
    """Run named checks against an .infrahub.yml output and return skillgrade JSON.

    ``py_path`` is optional: error-surface checks inspect a Python check file
    rather than the config, and receive it as ``tree`` / ``py_raw``.
    """
    config, _ = load_output(output_path)
    tree, py_raw = load_output_py(py_path) if py_path else (None, "")

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(config, tree=tree, py_raw=py_raw)
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


def _traversed_node_blocks(gql: str) -> list[str]:
    """Selection set of every `node {` after the first (the filtered child's own).

    Excluding the first `node {` keeps the child's own `name { value }` from
    satisfying the fetch assertion, while returning *every* traversed block
    (not only the textually last one) so a correct answer whose comparison
    traversal is followed by a sibling selection still counts.
    """
    matches = list(re.finditer(r"node\s*{", gql))
    blocks: list[str] = []
    for m in matches[1:]:
        start = m.end() - 1  # index of the opening brace
        depth = 0
        for i in range(start, len(gql)):
            ch = gql[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(gql[start + 1 : i])
                    break
        else:
            blocks.append(gql[start + 1 :])  # unbalanced; grade against the remainder
    return blocks


def _skips_unresolvable_without_log(py: str) -> bool | None:
    """Does any `if` branch skip (continue/return) without logging first?

    Semantic, idiom-agnostic detection of the anti-pattern the rule forbids
    (`if dev is None: continue`), instead of matching guard syntax. Returns
    None when the source cannot be parsed, so the caller can fall back.
    """
    try:
        tree = ast.parse(textwrap.dedent(py))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        skips = any(isinstance(s, (ast.Continue, ast.Return)) for s in ast.walk(node))
        logged = any(
            isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "log_error"
            for c in ast.walk(node)
        )
        if skips and not logged:
            return True
    return False


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


def text_fetches_related_attribute_value(
    gql: str, py: str, attr: str = "status"
) -> tuple[bool, str]:
    """The *named* comparison attribute is selected inside a traversed related node.

    The assertion carries the rule's thesis — the comparison attribute has to
    be pulled in the same query — so it matches the attribute by name (default
    `status`). Fetching some other attribute (e.g. the parent's `name`) on the
    traversed node no longer passes, and the child's own attributes are
    excluded because the child's `node {` is skipped.
    """
    blocks = _traversed_node_blocks(gql)
    if not blocks:
        return False, "Query does not traverse into a related node"
    pattern = re.compile(rf"\b{re.escape(attr)}\s*\{{\s*value\b")
    if any(pattern.search(b) for b in blocks):
        return True, f"A traversed related node selects `{attr} {{ value }}` (parent state is fetched)"
    return False, f"No traversed related node selects `{attr} {{ value }}`; the comparison attribute is not fetched"


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
    """The relationship walk uses a null-guard idiom (`or {}` / `.get(k, {})`).

    Checks the idiom is present, not that every hop is covered (that would need
    to count hops against guards); the message says what it verifies.
    """
    if "or {}" in py or re.search(r"\.get\([^)]*,\s*{}\)", py):
        return True, "Relationship walk uses a null guard (`or {}` / `.get(k, {})`)"
    return False, "No null guard (`or {}` / `.get(k, {})`) on the relationship walk"


def text_flags_unresolvable_parent(gql: str, py: str) -> tuple[bool, str]:
    """An unresolvable related node is flagged, not silently skipped.

    Guards finding 2 semantically: any `if` branch that skips (continue/return)
    without a log_error is the anti-pattern (`if dev is None: continue`),
    regardless of how the condition is written. Passing also requires a
    log_error somewhere, so the unresolvable case is actually surfaced.
    """
    skips = _skips_unresolvable_without_log(py)
    if skips is None:  # unparseable — fall back to the classic textual anti-pattern
        classic = re.search(r"(is\s+None|if\s+not\s+[\w.\[\]()]+)\s*:\s*\n\s*(continue|return)\b", py)
        skips = bool(classic)
    if skips:
        return False, "An unresolvable-relationship branch skips (continue/return) without log_error"
    if not re.search(r"log_error\s*\(", py):
        return False, "No log_error on the unresolvable-relationship path"
    return True, "Flags an unresolvable related node instead of skipping it"


TEXT_CHECKS: dict[str, Any] = {
    "uses-sdk-execute-graphql": check_uses_sdk_execute_graphql,
    "no-status-code-branch": check_no_status_code_branch,
    "catches-graphql-error": check_catches_graphql_error,
    "child-status-filter": text_child_status_filter,
    "traverses-related-node": text_traverses_related_node,
    "fetches-related-attribute-value": text_fetches_related_attribute_value,
    "uses-infrahubcheck": text_uses_infrahubcheck,
    "surfaces-violation": text_surfaces_violation,
    "null-safe-traversal": text_null_safe_traversal,
    "flags-unresolvable-parent": text_flags_unresolvable_parent,
}


def run_text_checks(
    check_names: list[str], sources: dict[str, str], attr: str = "status"
) -> dict:
    """Run named TEXT_CHECKS against produced source files and return skillgrade JSON.

    `sources` maps a label (e.g. "gql", "py") to that file's raw text. `attr` is
    the comparison attribute the query must fetch on the related node, passed to
    the fetch check so it stays generic per task rather than hardcoded.
    """
    gql = sources.get("gql", "")
    py = sources.get("py", "")

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = TEXT_CHECKS[name]
        try:
            if name == "fetches-related-attribute-value":
                ok, msg = fn(gql, py, attr)
            else:
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
