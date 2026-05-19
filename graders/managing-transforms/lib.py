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


def has_post_to_artifact_generate(
    tree: ast.Module | None, py_raw: str = ""
) -> bool:
    """True if the source POSTs to ``/api/artifact/generate``.

    Two detection strategies:

    1. **Direct AST match** — any ``<expr>.post(...)`` call whose
       positional arg[0] or ``url``/``path``/``endpoint`` kwarg is
       a string literal (or f-string) containing the path. Catches
       ``client.post("/api/artifact/generate/...")``,
       ``httpx.post(url=f"...")``, etc.

    2. **Fallback text+call match** — if (1) doesn't fire, accept
       the case where the source contains both *some* ``.post(``
       call AND a string literal containing ``/api/artifact/generate``
       (possibly stored in a variable, a constant, or built via
       multiple f-string fragments the AST helper can't reassemble).
       This is fuzzier but catches realistic patterns the model
       produces, e.g. ``endpoint = f"...{def_id}..."; await client.post(endpoint)``.
    """
    if tree is None:
        return False
    # Strategy 1: direct AST match
    has_any_post = False
    for call in _iter_calls(tree):
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr == "post"):
            continue
        has_any_post = True
        candidates: list[ast.AST] = list(call.args[:1])
        for kw in call.keywords:
            if kw.arg in ("url", "path", "endpoint"):
                candidates.append(kw.value)
        for c in candidates:
            if _string_contains(c, _ARTIFACT_GENERATE_PATH):
                return True
    # Strategy 2: fallback — a .post() call somewhere AND the path
    # appears as a string literal anywhere in the file.
    if has_any_post and py_raw and _ARTIFACT_GENERATE_PATH in py_raw:
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
# Union-fragments checks
# ---------------------------------------------------------------------------

# Known union-typed relationships in Infrahub base schema. The
# grader is intentionally narrow — extend this dict when new
# unions enter the eval corpus.
_KNOWN_UNION_RELATIONSHIPS = {
    "location": ("name", "shortname"),  # rel name -> divergent fields
}


def check_query_uses_inline_fragments_for_location(
    gql_text: str = "", **_: Any
) -> tuple[bool, str]:
    """If the query touches ``location``, it must contain at least one
    ``... on Location<...>`` inline fragment.
    """
    if not gql_text:
        return False, "No GraphQL output to inspect"
    block = block_for_relationship(gql_text, "location")
    if block is None:
        return False, "Query does not touch 'location' relationship"
    fragments = find_inline_fragments(block)
    if any(f.startswith("Location") for f in fragments):
        return True, f"Uses inline fragments: {fragments}"
    return False, "location { ... } contains no ... on Location<Type> fragment"


def check_query_no_direct_field_on_union_location(
    gql_text: str = "", **_: Any
) -> tuple[bool, str]:
    """The query must not select ``name``/``shortname`` directly on
    the ``location`` union (the bug 1 pattern).
    """
    if not gql_text:
        return False, "No GraphQL output to inspect"
    bad: list[str] = []
    for field in _KNOWN_UNION_RELATIONSHIPS["location"]:
        if field_appears_directly_under_union(gql_text, "location", field):
            bad.append(field)
    if bad:
        return False, f"Direct field(s) on union location.node: {', '.join(bad)}"
    return True, "No direct field selections on union location.node"


# ---------------------------------------------------------------------------
# Artifact regen polling checks
# ---------------------------------------------------------------------------


def check_posts_artifact_generate_endpoint(
    tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """Source must contain a POST whose URL mentions /api/artifact/generate."""
    if tree is None:
        return False, "No Python source to inspect"
    if has_post_to_artifact_generate(tree, py_raw):
        return True, "POST to /api/artifact/generate found"
    # Include a short preview on failure so CI logs surface why we missed.
    # Encode newlines so the JSON payload stays single-line in skillgrade.
    preview = (py_raw[:400] or "<empty>").replace("\n", "\\n")
    return False, f"No POST to /api/artifact/generate found. py_raw[:400]={preview}"


def check_has_polling_loop(
    tree: ast.Module | None = None, **_: Any
) -> tuple[bool, str]:
    """Source must contain at least one ``while``/``for``/``async for`` loop."""
    if tree is None:
        return False, "No Python source to inspect"
    if has_loop_construct(tree):
        return True, "Loop construct found"
    return False, "No loop construct found — fire-and-forget pattern"


def check_polls_coreartifact_after_post(
    tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """Source must reference ``kind="CoreArtifact"`` in a call (a read)."""
    if tree is None:
        return False, "No Python source to inspect"
    if not has_post_to_artifact_generate(tree, py_raw):
        return False, "No POST to /api/artifact/generate; nothing to poll"
    if references_core_artifact_in_call(tree):
        return True, "CoreArtifact read found after POST"
    return False, "No call references kind='CoreArtifact'"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "query-uses-inline-fragments-for-location": check_query_uses_inline_fragments_for_location,
    "query-no-direct-field-on-union-location": check_query_no_direct_field_on_union_location,
    "posts-artifact-generate-endpoint": check_posts_artifact_generate_endpoint,
    "has-polling-loop": check_has_polling_loop,
    "polls-coreartifact-after-post": check_polls_coreartifact_after_post,
}


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
