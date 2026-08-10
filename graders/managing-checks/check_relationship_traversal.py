#!/usr/bin/env python3
"""Grader for the relationship-traversal-check eval task.

Unlike the registration graders in this directory, this task grades the
*query and Python logic* of a check that validates a node against a
related node's state, so it reads the produced `output.gql` and
`output.py` directly rather than an `.infrahub.yml` via run_checks.

The load-bearing, deterministic fact is the query shape: a check runs
one query with no lazy fetch, so the parent's comparison attribute must
be pulled by traversing the relationship inside the query. The naive
failure mode — selecting only the child — is exactly what these query
assertions catch. The validate() assertions confirm the violation is
surfaced and the nested unwrap is null-safe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _read(name: str) -> str:
    try:
        return Path(name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def check_child_status_filter(gql: str, py: str) -> tuple[bool, str]:
    """The query filters the child set by an attribute value (e.g. status__value:)."""
    if re.search(r"\w+__value\s*:", gql):
        return True, "Query filters children by an attribute value"
    return False, "Query has no `<attr>__value:` filter selecting the constrained children"


def check_traverses_related_node(gql: str, py: str) -> tuple[bool, str]:
    """The query nests into a related node (>= 2 `node {` blocks)."""
    opens = len(re.findall(r"node\s*{", gql))
    if opens >= 2:
        return True, f"Query nests into a related node ({opens} `node {{` blocks)"
    return False, "Query does not traverse a relationship into a nested `node {` block"


def check_fetches_related_attribute_value(gql: str, py: str) -> tuple[bool, str]:
    """An attribute `value` is selected inside a nested relationship, not just at the top."""
    node_opens = [m.start() for m in re.finditer(r"node\s*{", gql)]
    if len(node_opens) < 2:
        return False, "No nested node block to hold the related attribute"
    after_second = gql[node_opens[1]:]
    if re.search(r"\bvalue\b", after_second):
        return True, "Related node selects an attribute value (parent state is fetched)"
    return False, "Nested related node does not select any attribute `value` to compare against"


def check_uses_infrahubcheck(gql: str, py: str) -> tuple[bool, str]:
    """Python defines an InfrahubCheck subclass bound to a query."""
    if "InfrahubCheck" in py and re.search(r"query\s*=", py):
        return True, "Defines an InfrahubCheck with a `query =` binding"
    return False, "No InfrahubCheck subclass with a `query =` attribute"


def check_surfaces_violation(gql: str, py: str) -> tuple[bool, str]:
    """validate() surfaces the mismatch via log_error (blocks the merge)."""
    if re.search(r"log_error\s*\(", py):
        return True, "Reports the violation with log_error"
    return False, "validate() never calls log_error, so no violation is surfaced"


def check_null_safe_traversal(gql: str, py: str) -> tuple[bool, str]:
    """The nested unwrap guards against a null relationship."""
    if "or {}" in py or re.search(r"is\s+None", py):
        return True, "Guards the relationship walk against a null hop"
    return False, "No null guard (`or {}` / `is None`) on the nested relationship walk"


CHECKS = [
    ("child-status-filter", check_child_status_filter),
    ("traverses-related-node", check_traverses_related_node),
    ("fetches-related-attribute-value", check_fetches_related_attribute_value),
    ("uses-infrahubcheck", check_uses_infrahubcheck),
    ("surfaces-violation", check_surfaces_violation),
    ("null-safe-traversal", check_null_safe_traversal),
]


def main() -> None:
    gql = _read("output.gql")
    py = _read("output.py")

    entries = []
    passed = 0
    for name, fn in CHECKS:
        try:
            ok, msg = fn(gql, py)
        except Exception as exc:  # pragma: no cover
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(CHECKS)
    score = round(passed / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"All {total} checks passed."
        if not failed
        else f"{passed}/{total} checks passed. Failed: {', '.join(failed)}"
    )
    print(json.dumps({"score": score, "details": details, "checks": entries}))


if __name__ == "__main__":
    main()
