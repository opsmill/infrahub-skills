"""Shared grader library for infrahub-managing-generators evaluations.

Provides Python AST parsing helpers, individual assertion check
functions, a CHECKS registry, and the top-level ``run_checks``
function that returns skillgrade JSON format.

Graders for this skill parse Python source (the generator class
the model produced as ``output.py``) rather than YAML. Some
expressions cannot be resolved from AST alone — variable
references, function-call results — and the check functions
treat those as "indeterminate" (passing) rather than failing.
The checks fail only on shapes that are demonstrably wrong:
bare string literals where a dict reference is required,
over-packed list literals, list literals passed to ``.add()``.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["relationship-hfid-form-correct", "no-bare-string-relationship"],
        Path("output.py"),
    )
    print(result)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output_py(path: Path) -> tuple[ast.Module | None, str]:
    """Load a Python source file and return ``(parsed_tree, raw_text)``.

    Returns ``(None, "")`` if the file does not exist.
    Returns ``(None, raw)`` if the file exists but has a syntax error.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None, ""
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return None, raw
    return tree, raw


# ---------------------------------------------------------------------------
# CHECKS registry (populated by later tasks)
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_path: Path,
) -> dict:
    """Run named checks against a Python source file.

    Returns skillgrade JSON: ``{"score": float, "details": str,
    "checks": [...]}``.

    Raises ``KeyError`` if any name in ``check_names`` is not in
    ``CHECKS``.
    """
    tree, raw = load_output_py(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            ok, msg = fn(tree, raw_text=raw)
        except Exception as exc:  # defensive — never let one check crash all
            ok, msg = False, f"Error running check: {exc}"

        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0

    failed_names = [e["name"] for e in entries if not e["passed"]]
    if failed_names:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed_names)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}
