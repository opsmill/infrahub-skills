"""Shared grader library for infrahub-managing-transforms evaluations.

Provides text-parsing helpers for ``.gql`` files, Python AST
helpers for ``.py`` files, individual check functions, a
``CHECKS`` registry, and the top-level ``run_checks`` entry
point that returns skillgrade JSON.

Two output kinds are supported:

- ``output.gql`` — raw GraphQL query text. The union-fragments
  checks use simple regex/text matching rather than a full
  GraphQL parser; this is fragile by design but cheap and
  matches the failure shape we care about.
- ``output.py`` — Python source for the artifact-regen polling
  eval. Checks use AST parsing.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["query-uses-inline-fragments-for-location"],
        {"gql": Path("output.gql")},
    )
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output_gql(path: Path) -> str:
    """Load a GraphQL query file. Returns empty string on missing file."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


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
# GraphQL text helpers
# ---------------------------------------------------------------------------


_INLINE_FRAGMENT_RE = re.compile(r"\.\.\.\s*on\s+([A-Za-z_][A-Za-z0-9_]*)")


def find_inline_fragments(gql_text: str) -> list[str]:
    """Return all type names appearing in ``... on <TypeName>``."""
    return _INLINE_FRAGMENT_RE.findall(gql_text or "")


def _find_balanced_block(text: str, start: int) -> str | None:
    """Given an index pointing at ``{``, return the substring up to
    the matching ``}`` (inclusive). Returns ``None`` on imbalance.
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def block_for_relationship(gql_text: str, rel_name: str) -> str | None:
    """Return the text of ``<rel_name> { ... }`` (first occurrence)."""
    pattern = re.compile(rf"\b{re.escape(rel_name)}\s*\{{")
    match = pattern.search(gql_text or "")
    if not match:
        return None
    return _find_balanced_block(gql_text, match.end() - 1)


def field_appears_directly_under_union(
    gql_text: str, rel_name: str, field: str
) -> bool:
    """Heuristic: does the query select ``<field>`` inside
    ``<rel_name> { node { ... } }`` *without* a preceding
    ``... on <Type>`` fragment in that same node block?

    Returns ``False`` if the relationship isn't queried at all,
    or if the query uses inline fragments around the field.
    """
    block = block_for_relationship(gql_text, rel_name)
    if block is None:
        return False
    # Find the inner `node { ... }` block
    node_match = re.search(r"\bnode\s*\{", block)
    if not node_match:
        return False
    node_block = _find_balanced_block(block, node_match.end() - 1)
    if node_block is None:
        return False
    # If there are inline fragments inside this node block, treat as safe.
    if find_inline_fragments(node_block):
        return False
    # Otherwise, does the field appear as a direct sub-selection?
    field_pattern = re.compile(rf"\b{re.escape(field)}\s*\{{")
    return bool(field_pattern.search(node_block))


# ---------------------------------------------------------------------------
# Python AST helpers
# ---------------------------------------------------------------------------


def _iter_calls(tree: ast.Module) -> Iterator[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


_ARTIFACT_GENERATE_PATH = "/api/artifact/generate"


def _string_contains(node: ast.AST, needle: str) -> bool:
    """True if ``node`` is a string literal or f-string containing ``needle``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return needle in node.value
    if isinstance(node, ast.JoinedStr):
        return any(
            isinstance(v, ast.Constant) and isinstance(v.value, str) and needle in v.value
            for v in node.values
        )
    return False


def has_post_to_artifact_generate(tree: ast.Module | None) -> bool:
    """True if any ``post(...)`` call's URL argument mentions
    ``/api/artifact/generate``.

    Accepts any callee whose attribute name is ``post`` —
    ``httpx.post``, ``requests.post``, ``client.post``,
    ``self.client.post``, etc. Inspects positional arg[0] and
    keyword args ``url`` / ``path`` for the substring.
    """
    if tree is None:
        return False
    for call in _iter_calls(tree):
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr == "post"):
            continue
        candidates: list[ast.AST] = list(call.args[:1])
        for kw in call.keywords:
            if kw.arg in ("url", "path", "endpoint"):
                candidates.append(kw.value)
        for c in candidates:
            if _string_contains(c, _ARTIFACT_GENERATE_PATH):
                return True
    return False


def has_loop_construct(tree: ast.Module | None) -> bool:
    """True if ``ast.While`` or ``ast.For`` (sync or async) is in tree."""
    if tree is None:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
            return True
    return False


def references_core_artifact_in_call(tree: ast.Module | None) -> bool:
    """True if any call passes ``kind="CoreArtifact"`` as a keyword arg."""
    if tree is None:
        return False
    for call in _iter_calls(tree):
        for kw in call.keywords:
            if kw.arg == "kind" and isinstance(kw.value, ast.Constant):
                if kw.value.value == "CoreArtifact":
                    return True
    return False


# ---------------------------------------------------------------------------
# CHECKS registry (populated by later tasks)
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_paths: dict[str, Path],
) -> dict:
    """Run named checks against one or more output files.

    Parameters
    ----------
    check_names:
        List of assertion names from ``CHECKS``.
    output_paths:
        Mapping of output kind to path. Recognised keys: ``"gql"``,
        ``"py"``. Each check function declares which input it
        needs via ``**kwargs``.

    Returns skillgrade JSON ``{"score", "details", "checks"}``.
    Raises ``KeyError`` if any check name is unknown.
    """
    gql_text = load_output_gql(output_paths.get("gql", Path("output.gql")))
    tree, py_raw = load_output_py(output_paths.get("py", Path("output.py")))

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(gql_text=gql_text, tree=tree, py_raw=py_raw)
        except Exception as exc:  # defensive — never let one check crash all
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
