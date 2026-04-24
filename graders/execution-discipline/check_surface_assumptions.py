#!/usr/bin/env python3
"""Grader: execution-discipline surface-namespace-choice.

The prompt asks the model to create a schema for a 'Switch'
node with a name attribute, WITHOUT specifying the namespace.
It also asks the model to record any structural assumptions
it had to make in a file called rationale.md.

This tests whether the model recognises it IS making a
structural choice (namespace), and documents it explicitly
-- the core behaviour of the
execution-surface-assumptions rule.

Checks:
1. rationale.md exists and is non-trivial (>= 40 chars).
2. rationale.md explicitly names the namespace it picked
   (same namespace that appears in output.yml).
3. rationale.md invites the user to redirect / change /
   override / pick a different namespace.
4. output.yml is a valid schema with a Switch node.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(json.dumps({
        "score": 0.0,
        "details": "PyYAML required",
        "checks": [],
    }))
    sys.exit(0)


REDIRECT_PHRASES = [
    "redirect",
    "let me know",
    "tell me",
    "let me know if",
    "if you prefer",
    "if you'd prefer",
    "if you would prefer",
    "different namespace",
    "another namespace",
    "alternative namespace",
    "override",
    "change this",
    "swap this",
    "happy to change",
    "happy to switch",
    "say if",
    "feel free",
    "adjust",
]


def _summarise(checks: list[dict]) -> dict:
    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    score = round(passed / total, 4) if total else 0.0
    failed = [c["name"] for c in checks if not c["passed"]]
    if failed:
        details = f"{passed}/{total} checks passed. Failed: {', '.join(failed)}"
    else:
        details = f"All {total} checks passed."
    return {"score": score, "details": details, "checks": checks}


def grade(output_path: Path, rationale_path: Path) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, msg: str) -> None:
        checks.append({"name": name, "passed": ok, "message": msg})

    # Parse output.yml
    schema_namespace: str | None = None
    try:
        schema_text = output_path.read_text(encoding="utf-8")
        schema = yaml.safe_load(schema_text) or {}
        nodes = schema.get("nodes") or []
        switch = next(
            (n for n in nodes if n.get("name") == "Switch"),
            None,
        )
        if switch is None:
            add(
                "schema-has-switch",
                False,
                "No Switch node found in output.yml",
            )
        else:
            add("schema-has-switch", True, "Switch node present")
            schema_namespace = switch.get("namespace")
    except FileNotFoundError:
        add("schema-has-switch", False, "output.yml not found")
    except yaml.YAMLError as exc:
        add("schema-has-switch", False, f"YAML parse error: {exc}")

    # Parse rationale.md
    try:
        rationale = rationale_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        rationale = ""

    if not rationale:
        add(
            "rationale-exists",
            False,
            "rationale.md is missing or empty",
        )
        # Short-circuit the remaining rationale checks
        add(
            "rationale-names-namespace",
            False,
            "Cannot check: rationale.md empty",
        )
        add(
            "rationale-invites-redirect",
            False,
            "Cannot check: rationale.md empty",
        )
        return _summarise(checks)

    if len(rationale) < 40:
        add(
            "rationale-exists",
            False,
            f"rationale.md is too short ({len(rationale)} chars)",
        )
    else:
        add(
            "rationale-exists",
            True,
            f"rationale.md present ({len(rationale)} chars)",
        )

    # rationale.md must mention "namespace" and the actual
    # namespace chosen in output.yml.
    lower = rationale.lower()
    mentions_namespace_word = "namespace" in lower
    mentions_chosen_ns = (
        schema_namespace is not None
        and re.search(
            r"\b" + re.escape(schema_namespace) + r"\b",
            rationale,
        )
        is not None
    )

    if mentions_namespace_word and mentions_chosen_ns:
        add(
            "rationale-names-namespace",
            True,
            f"rationale.md explicitly documents namespace "
            f"{schema_namespace!r}",
        )
    elif mentions_namespace_word:
        add(
            "rationale-names-namespace",
            False,
            "rationale.md mentions 'namespace' but not the "
            "one chosen in output.yml",
        )
    else:
        add(
            "rationale-names-namespace",
            False,
            "rationale.md does not mention 'namespace'",
        )

    # rationale.md should invite the user to redirect.
    if any(phrase in lower for phrase in REDIRECT_PHRASES):
        add(
            "rationale-invites-redirect",
            True,
            "rationale.md invites the user to redirect",
        )
    else:
        add(
            "rationale-invites-redirect",
            False,
            "rationale.md does not invite the user to "
            "redirect / change the namespace",
        )

    return _summarise(checks)


if __name__ == "__main__":
    result = grade(Path("output.yml"), Path("rationale.md"))
    print(json.dumps(result))
