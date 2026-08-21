"""Shared grader library for infrahub-managing-transforms evaluations.

Provides text-parsing helpers for ``.gql`` files, Python AST
helpers for ``.py`` files, individual check functions, a
``CHECKS`` registry, and the top-level ``run_checks`` entry
point that returns skillgrade JSON.

Four output kinds are supported:

- ``output.gql`` — raw GraphQL query text. The union-fragments
  checks use simple regex/text matching rather than a full
  GraphQL parser; this is fragile by design but cheap and
  matches the failure shape we care about.
- ``output.py`` — Python source for the artifact-regen polling
  eval. Checks use AST parsing.
- ``output.md`` — a workflow plan (Markdown). The pre-merge
  dry-run checks scan it for the dry-run command and pre-merge
  framing.
- ``output.yml`` — an ``.infrahub.yml`` manifest for the
  watch.files eval. Checks inspect the parsed mapping to see
  which dependencies each transform declares.

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

import yaml


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output_gql(path: Path) -> str:
    """Load a GraphQL query file. Returns empty string on missing file."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def load_output_md(path: Path) -> str:
    """Load a Markdown/plan file. Returns empty string on missing file."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return ""


_YAML_FENCE = re.compile(r"^```(?:yaml|yml)\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def load_output_yaml(path: Path) -> dict:
    """Load an ``.infrahub.yml`` manifest and return the parsed mapping.

    Returns ``{}`` when the file is missing, unparseable, or not a
    mapping. A document wrapped in a ```yaml fence is unwrapped first,
    so a model that formats its answer as a code block still grades.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    fence = _YAML_FENCE.search(raw)
    if fence:
        raw = fence.group(1)
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    return doc if isinstance(doc, dict) else {}


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


def _is_post_like_method(attr_name: str) -> bool:
    """True if ``attr_name`` is any plausible HTTP-POST method name.

    Matches ``post`` (httpx/requests/aiohttp public method),
    ``_post`` (infrahub_sdk's private helper), and anything else
    ending in ``post`` (``do_post``, ``async_post``, etc.).
    """
    return attr_name.endswith("post")


def has_post_to_artifact_generate(
    tree: ast.Module | None, py_raw: str = ""
) -> bool:
    """True if the source POSTs to ``/api/artifact/generate``.

    Two detection strategies:

    1. **Direct AST match** — any call to a method whose name ends in
       ``post`` (``post``, ``_post``, etc.) where the URL is a string
       literal (or f-string) containing the path. Catches the public
       HTTP-client ``.post(url)`` pattern and the SDK's private
       ``client._post(url=..., payload=...)`` pattern alike.

    2. **Fallback text+call match** — if (1) doesn't fire, accept
       the case where the source contains both *some* post-like call
       AND the path as a string anywhere in the file. Covers
       realistic LLM output like
       ``endpoint = f"...{def_id}..."; await client._post(endpoint)``.
    """
    if tree is None:
        return False
    has_any_post = False
    for call in _iter_calls(tree):
        func = call.func
        if not (isinstance(func, ast.Attribute) and _is_post_like_method(func.attr)):
            continue
        has_any_post = True
        candidates: list[ast.AST] = list(call.args[:1])
        for kw in call.keywords:
            if kw.arg in ("url", "path", "endpoint"):
                candidates.append(kw.value)
        for c in candidates:
            if _string_contains(c, _ARTIFACT_GENERATE_PATH):
                return True
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
    return False, "No POST to /api/artifact/generate found"


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
# Pre-merge GraphQL dry-run checks (deployment-gql-dry-run common rule)
# ---------------------------------------------------------------------------

# The plan must dry-run the changed query by *executing* it against a live
# schema — `infrahubctl render` for a transform, or running the check /
# generator that owns the query — not rely on static `schema check` alone.
_DRY_RUN_CMD_PATTERNS = [
    re.compile(r"infrahubctl\s+render\b", re.IGNORECASE),
    re.compile(r"infrahubctl\s+(?:check|generator)\s+run\b", re.IGNORECASE),
]

# The dry-run must be framed as a pre-merge gate (before opening / merging
# the PR), which is the whole point of the rule.
_PRE_MERGE_PATTERNS = [
    re.compile(r"\bpre[-\s]?merge\b", re.IGNORECASE),
    re.compile(r"\bbefore\s+(?:you\s+)?merg\w+\b", re.IGNORECASE),
    re.compile(r"\bbefore\s+opening\b", re.IGNORECASE),
    re.compile(r"\bbefore\s+the\s+(?:pr|pull request)\b", re.IGNORECASE),
    re.compile(r"\bprior\s+to\s+merg\w+\b", re.IGNORECASE),
    re.compile(
        r"\bbefore\s+(?:you\s+)?(?:open|rais\w+|submit\w*)\b[^.\n]{0,40}"
        r"\b(?:pr|pull request|proposed change|merge)\b",
        re.IGNORECASE,
    ),
]


def check_dry_run_executes_query(md_text: str = "", **_: Any) -> tuple[bool, str]:
    """Plan must dry-run the query live (render / check run / generator run),
    not rely on static ``schema check`` alone."""
    if not md_text:
        return False, "No plan text to inspect"
    for pat in _DRY_RUN_CMD_PATTERNS:
        if pat.search(md_text):
            return True, f"Dry-runs the query live (matched {pat.pattern!r})"
    return False, (
        "No live dry-run command (infrahubctl render / check run / "
        "generator run) — static schema check alone misses GQL mismatches"
    )


def check_dry_run_before_merge(md_text: str = "", **_: Any) -> tuple[bool, str]:
    """Plan must frame the dry-run as a pre-merge / pre-PR step."""
    if not md_text:
        return False, "No plan text to inspect"
    for pat in _PRE_MERGE_PATTERNS:
        if pat.search(md_text):
            return True, f"Frames dry-run as pre-merge (matched {pat.pattern!r})"
    return False, "Does not frame the dry-run as a pre-merge / pre-PR gate"


# ---------------------------------------------------------------------------
# watch.files checks (artifacts-watch-dependencies)
# ---------------------------------------------------------------------------
#
# Fixture-coupled, like the union-fragment checks above: the eval task hands
# the model a repo whose transforms/ holds device_config.py (importing the
# sibling .device_config_query and my_package.formatting from src/) and the
# self-contained interface_names.py, plus one Jinja2 template whose includes
# are all literal and one that resolves its partial through a variable.

_WATCH_SECTIONS = ("python_transforms", "jinja2_transforms", "generator_definitions")


def _entries(yml_doc: dict, section: str) -> list[dict]:
    """Return the mapping entries of a manifest section."""
    items = yml_doc.get(section) or []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _entry_named(yml_doc: dict, section: str, name: str) -> dict | None:
    for entry in _entries(yml_doc, section):
        if entry.get("name") == name:
            return entry
    return None


def canonical_watch_path(path: str) -> str:
    """Normalize a watch entry the way Infrahub's canonicalizer does."""
    normalized = str(path).replace("\\", "/")
    while True:
        previous = normalized
        normalized = normalized.lstrip("/").removeprefix("./").rstrip("/")
        if normalized == previous:
            return normalized


def watch_files(entry: dict) -> list[str] | None:
    """Return an entry's canonicalized ``watch.files``.

    ``None`` means the entry carries no ``watch`` key at all, which is the
    case the rule treats as "regenerates on every commit". A ``watch`` in
    any shape other than a mapping with a ``files`` list — the bare-list
    form Infrahub rejects at import — also returns ``None``, and is caught
    separately by ``check_watch_uses_object_form``.
    """
    if "watch" not in entry:
        return None
    watch = entry["watch"]
    if not isinstance(watch, dict):
        return None
    files = watch.get("files")
    if not isinstance(files, list):
        return None
    return [canonical_watch_path(f) for f in files if isinstance(f, str)]


def _covers(files: list[str], target: str) -> bool:
    """True if ``target`` is named outright or sits under a declared directory."""
    target = canonical_watch_path(target)
    return any(target == f or target.startswith(f"{f}/") for f in files)


def check_watch_present_on_python_transforms(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """Every python_transforms entry must carry a watch key.

    Without one the fingerprint folds in the commit id and the artifacts
    re-render on every commit.
    """
    entries = _entries(yml_doc or {}, "python_transforms")
    if not entries:
        return False, "No python_transforms entries found to inspect"
    missing = [e.get("name", "<unnamed>") for e in entries if "watch" not in e]
    if missing:
        return False, f"python_transforms entries with no watch key: {', '.join(missing)}"
    return True, f"All {len(entries)} python_transforms entries declare watch"


def check_watch_uses_object_form(yml_doc: dict | None = None, **_: Any) -> tuple[bool, str]:
    """Every watch must be ``{files: [...]}``; the bare-list form fails import."""
    doc = yml_doc or {}
    for section in _WATCH_SECTIONS:
        for entry in _entries(doc, section):
            if "watch" not in entry:
                continue
            name = entry.get("name", "<unnamed>")
            watch = entry["watch"]
            if not isinstance(watch, dict):
                return False, (
                    f"{section}/{name}: watch is {type(watch).__name__}, not an object — "
                    "the bare-list form is rejected when the repository is imported"
                )
            unknown = set(watch) - {"files"}
            if unknown:
                return False, f"{section}/{name}: unknown key(s) under watch: {sorted(unknown)}"
            if not isinstance(watch.get("files"), list):
                return False, f"{section}/{name}: watch.files is not a list"
    return True, "Every watch block uses the object form with a files list"


def check_watch_declares_sibling_import(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """device_config imports .device_config_query, so it must be declared.

    Sharing a directory is not a dependency relationship: imports are never
    followed, and the directory listing that used to cover siblings is being
    withdrawn (opsmill/infrahub#9644).
    """
    entry = _entry_named(yml_doc or {}, "python_transforms", "device_config")
    if entry is None:
        return False, "No python_transforms entry named device_config"
    files = watch_files(entry)
    if files is None:
        return False, "device_config declares no usable watch.files"
    if _covers(files, "transforms/device_config_query.py"):
        return True, "device_config declares its sibling query model"
    return False, (
        "device_config does not declare the sibling module it imports "
        f"(transforms/device_config_query.py); watch.files = {files}"
    )


def check_watch_declares_outside_package_import(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """device_config imports my_package.formatting, which lives under src/."""
    entry = _entry_named(yml_doc or {}, "python_transforms", "device_config")
    if entry is None:
        return False, "No python_transforms entry named device_config"
    files = watch_files(entry)
    if files is None:
        return False, "device_config declares no usable watch.files"
    if _covers(files, "src/my_package/formatting.py"):
        return True, "device_config declares the shared src/ package it imports"
    return False, (
        "device_config does not declare src/my_package/formatting.py (or the "
        f"package holding it); watch.files = {files}"
    )


def check_watch_empty_for_self_contained(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """interface_names has no first-party import, so it declares an empty list.

    ``files: []`` is the assertion that there is nothing to declare; it is
    what stops the commit id being folded into the fingerprint.
    """
    entry = _entry_named(yml_doc or {}, "python_transforms", "interface_names")
    if entry is None:
        return False, "No python_transforms entry named interface_names"
    files = watch_files(entry)
    if files is None:
        return False, "interface_names declares no usable watch.files (expected [])"
    if files == []:
        return True, "interface_names declares an explicit empty watch.files"
    return False, (
        "interface_names imports nothing first-party, so watch.files should be "
        f"empty; got {files}"
    )


def check_watch_omitted_for_static_jinja2(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """A Jinja2 transform whose includes are all literal needs no watch.

    Its closure is built by parsing the template and following every
    reference, so it is trusted on its own.
    """
    entry = _entry_named(yml_doc or {}, "jinja2_transforms", "arista_startup_config")
    if entry is None:
        return False, "No jinja2_transforms entry named arista_startup_config"
    files = watch_files(entry)
    if "watch" not in entry or files == []:
        return True, "arista_startup_config carries no superfluous watch entries"
    return False, (
        "arista_startup_config includes only literal templates, so its closure is "
        f"already complete; the watch entries are noise: {files}"
    )


def check_watch_declares_dynamic_jinja2_partials(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """A template that resolves its partial through a variable needs watch.

    The parser cannot follow ``{% include partial_name %}``, so the closure
    is incomplete until the candidate partials are declared.
    """
    entry = _entry_named(yml_doc or {}, "jinja2_transforms", "cisco_startup_config")
    if entry is None:
        return False, "No jinja2_transforms entry named cisco_startup_config"
    files = watch_files(entry)
    if files is None:
        return False, "cisco_startup_config declares no usable watch.files"
    if _covers(files, "templates/partials/header.j2"):
        return True, "cisco_startup_config declares the partials its dynamic include can reach"
    return False, (
        "cisco_startup_config resolves its partial through a variable but does not "
        f"declare templates/partials/; watch.files = {files}"
    )


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "query-uses-inline-fragments-for-location": check_query_uses_inline_fragments_for_location,
    "query-no-direct-field-on-union-location": check_query_no_direct_field_on_union_location,
    "posts-artifact-generate-endpoint": check_posts_artifact_generate_endpoint,
    "has-polling-loop": check_has_polling_loop,
    "polls-coreartifact-after-post": check_polls_coreartifact_after_post,
    "dry-run-executes-query": check_dry_run_executes_query,
    "dry-run-before-merge": check_dry_run_before_merge,
    "watch-present-on-python-transforms": check_watch_present_on_python_transforms,
    "watch-uses-object-form": check_watch_uses_object_form,
    "watch-declares-sibling-import": check_watch_declares_sibling_import,
    "watch-declares-outside-package-import": check_watch_declares_outside_package_import,
    "watch-empty-for-self-contained": check_watch_empty_for_self_contained,
    "watch-omitted-for-static-jinja2": check_watch_omitted_for_static_jinja2,
    "watch-declares-dynamic-jinja2-partials": check_watch_declares_dynamic_jinja2_partials,
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
        ``"py"``, ``"md"``, ``"yml"``. Each check function declares which
        input it needs via ``**kwargs``.

    Returns skillgrade JSON ``{"score", "details", "checks"}``.
    Raises ``KeyError`` if any check name is unknown.
    """
    gql_text = load_output_gql(output_paths.get("gql", Path("output.gql")))
    tree, py_raw = load_output_py(output_paths.get("py", Path("output.py")))
    md_text = load_output_md(output_paths.get("md", Path("output.md")))
    yml_doc = load_output_yaml(output_paths.get("yml", Path("output.yml")))

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(
                gql_text=gql_text,
                tree=tree,
                py_raw=py_raw,
                md_text=md_text,
                yml_doc=yml_doc,
            )
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
