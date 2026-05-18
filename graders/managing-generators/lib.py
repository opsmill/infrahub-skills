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
# AST helpers
# ---------------------------------------------------------------------------


def _iter_calls(tree: ast.Module) -> Iterator[ast.Call]:
    """Yield every ``ast.Call`` node anywhere in the tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _is_self_client_method(call: ast.Call, method: str) -> bool:
    """True if ``call.func`` is ``self.client.<method>``."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != method:
        return False
    if not isinstance(func.value, ast.Attribute) or func.value.attr != "client":
        return False
    if not isinstance(func.value.value, ast.Name) or func.value.value.id != "self":
        return False
    return True


def find_client_create_calls(tree: ast.Module) -> list[ast.Call]:
    """Return all ``self.client.create(...)`` call sites."""
    if tree is None:
        return []
    return [c for c in _iter_calls(tree) if _is_self_client_method(c, "create")]


def find_client_get_calls(tree: ast.Module) -> list[ast.Call]:
    """Return all ``self.client.get(...)`` call sites."""
    if tree is None:
        return []
    return [c for c in _iter_calls(tree) if _is_self_client_method(c, "get")]


def find_relationship_add_calls(tree: ast.Module) -> list[ast.Call]:
    """Return all ``<expr>.add(...)`` call sites.

    Does not filter by attribute path (``.members``, ``.peers``, etc.) —
    the check functions decide whether to narrow further.
    """
    if tree is None:
        return []
    return [
        c for c in _iter_calls(tree)
        if isinstance(c.func, ast.Attribute) and c.func.attr == "add"
    ]


def get_kwarg(call: ast.Call, name: str) -> ast.AST | None:
    """Return the value node for keyword argument ``name``, or None."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def get_data_dict_items(call: ast.Call) -> dict[str, ast.AST]:
    """If ``data=`` is a dict literal, return ``{key_str: value_ast}``.

    Returns ``{}`` if ``data`` is missing or not a literal dict.
    Non-string keys in the dict literal are skipped silently.
    """
    data = get_kwarg(call, "data")
    if not isinstance(data, ast.Dict):
        return {}
    items: dict[str, ast.AST] = {}
    for k, v in zip(data.keys, data.values):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            items[k.value] = v
    return items


def is_hfid_dict(node: ast.AST) -> tuple[bool, list[ast.AST] | None]:
    """True if ``node`` is ``{"hfid": [...]}`` with a list value.

    Returns ``(True, [element_ast_nodes])`` on match, else
    ``(False, None)``.
    """
    if not isinstance(node, ast.Dict):
        return False, None
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == "hfid":
            if isinstance(v, ast.List):
                return True, list(v.elts)
            return False, None
    return False, None


def is_id_dict(node: ast.AST) -> bool:
    """True if ``node`` is ``{"id": <expr>}``."""
    if not isinstance(node, ast.Dict):
        return False
    for k in node.keys:
        if isinstance(k, ast.Constant) and k.value == "id":
            return True
    return False


def is_bare_string(node: ast.AST) -> bool:
    """True if ``node`` is a bare string constant ``ast.Constant(value=str)``."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def is_name_or_attribute(node: ast.AST) -> bool:
    """True if ``node`` is a Name or Attribute reference (likely an SDK obj)."""
    return isinstance(node, (ast.Name, ast.Attribute))


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
