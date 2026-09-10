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
# schema, not rely on static `schema check` alone. Which command depends on
# what owns the query: `render` for a jinja2_transforms entry, `transform`
# for a python_transforms entry, or the check / generator itself. All three
# take their target as a positional argument. There is no `run` subcommand,
# and matching one here rewarded exactly the invented form
# skills/infrahub-common/rules/deployment-gql-dry-run.md exists to remove.
# A generic verb where the positional target belongs is an invented
# subcommand, not a name, so it does not count as a live dry-run. The verb
# has to be the *whole* token: `\b` ends at a hyphen, so it rejected
# kebab-case names whose first segment is a verb (`create-dc`, the fixture
# name a model may well hyphenate) and failed a correct answer.
_INVENTED_SUBCOMMAND = (
    r"(?!(?:run|list|get|create|delete|load|dump|check|validate|execute|"
    r"show|new|add|export|import)(?![\w-]))"
)
_DRY_RUN_CMD_PATTERNS = [
    re.compile(
        rf"infrahubctl\s+(?:render|transform|check|generator)\s+"
        rf"{_INVENTED_SUBCOMMAND}[a-z0-9][\w.-]*",
        re.IGNORECASE,
    ),
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
    """Plan must dry-run the query live, not rely on static ``schema check``.

    Live means executing the query: ``infrahubctl render <name>`` or
    ``transform <name>`` for the transform that owns it, or ``check <name>``
    / ``generator <name>`` for a check or generator. Each takes its target
    as a positional argument.
    """
    if not md_text:
        return False, "No plan text to inspect"
    for pat in _DRY_RUN_CMD_PATTERNS:
        if pat.search(md_text):
            return True, f"Dry-runs the query live (matched {pat.pattern!r})"
    return False, (
        "No live dry-run command (infrahubctl render/transform/check/"
        "generator <name>) — static schema check alone misses GQL mismatches"
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

    Without one — or with a bare ``watch:`` that parses to null — the
    fingerprint folds in the commit id and the artifacts re-render on
    every commit.
    """
    entries = _entries(yml_doc or {}, "python_transforms")
    if not entries:
        return False, "No python_transforms entries found to inspect"
    # ``watch:`` with nothing under it parses to null, which
    # ``fold_commit_id`` cannot tell apart from the key being absent. It
    # reads as a declaration without being one, so it fails like a
    # missing key rather than passing on the key's mere presence.
    missing = [
        e.get("name", "<unnamed>")
        for e in entries
        if e.get("watch") is None
    ]
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
    followed, and the directory listing that used to cover siblings was
    withdrawn in 1.11 (opsmill/infrahub#9644).
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


def check_watch_avoids_entry_directory(
    yml_doc: dict | None = None, **_: Any
) -> tuple[bool, str]:
    """No entry may watch the directory its own file_path sits in.

    Naming that directory re-creates the closure 1.10 built automatically and
    1.11 withdrew: every unrelated edit beside the entry point re-renders the
    artifacts. It also passes the declares-* checks for free, because a
    directory covers whatever sits under it — which is exactly why the answer
    has to be graded on it separately.
    """
    for entry in _entries(yml_doc or {}, "python_transforms"):
        files = watch_files(entry)
        if not files:
            continue
        file_path = canonical_watch_path(str(entry.get("file_path", "")))
        if "/" not in file_path:
            continue
        own_dir = file_path.rsplit("/", 1)[0]
        if own_dir in files:
            return False, (
                f"{entry.get('name', '<unnamed>')}: watch.files names its own directory "
                f"({own_dir}/), so every unrelated edit beside the entry point re-renders "
                "the artifacts; name the modules it actually imports"
            )
    return True, "No entry watches the directory holding its own file_path"


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


# ---------------------------------------------------------------------------
# Artifact content types
#
# `serialize_artifact_content` special-cases a dict ONLY for
# application/json and application/yaml; every other content type passes the
# payload through `str()`. So a dict returned for image/svg+xml is stored as
# a Python repr, silently. Verified against Infrahub 1.11.0.
# ---------------------------------------------------------------------------

# Calls whose result is a string regardless of the receiver. The second
# group is the idiomatic SVG-building routes: xml.etree, a jinja2 Template
# used inside a Python transform, textwrap, io.StringIO. A locally defined
# function of the same name wins over this list, so a helper named `render`
# is still classified by what it returns.
_STRING_CALLS = frozenset(
    {
        "join", "format", "strip", "lstrip", "rstrip", "replace", "upper", "lower",
        "dumps", "render", "dedent", "getvalue", "tostring",
    }
)


def _find_transform_def(
    tree: ast.Module | None,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the `transform` method definition, if the source has one."""
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "transform":
            return node
    return None


def _transform_returns(tree: ast.Module | None) -> list[ast.expr]:
    """Return every returned expression inside a `transform` method.

    Nested function definitions inside `transform` are skipped: their
    returns describe the helper, not the transform's own payload.
    """
    func = _find_transform_def(tree)
    if func is None:
        return []
    returns: list[ast.expr] = []
    nested = {
        n
        for child in func.body
        for n in ast.walk(child)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda)
    }
    nested_returns = {
        r for n in nested for r in ast.walk(n) if isinstance(r, ast.Return)
    }
    for inner in ast.walk(func):
        if (
            isinstance(inner, ast.Return)
            and inner.value is not None
            and inner not in nested_returns
        ):
            returns.append(inner.value)
    return returns


def _local_assignments(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, list[ast.expr]]:
    """Map each local name to every expression assigned to it.

    Parameters annotated `dict` are seeded as dicts, so `return data` and
    `str(data)` are classified from the signature the eval prompt hands
    the model. A parameter that is reassigned in the body loses the seed:
    the assignments describe it better than the annotation does.
    """
    assigned: dict[str, list[ast.expr]] = {}
    for node in ast.walk(func):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            targets, value = [node.target], node.value
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assigned.setdefault(target.id, []).append(value)
    args = func.args
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        annotation = arg.annotation
        is_dict = (isinstance(annotation, ast.Name) and annotation.id == "dict") or (
            isinstance(annotation, ast.Subscript)
            and isinstance(annotation.value, ast.Name)
            and annotation.value.id == "dict"
        )
        if is_dict and arg.arg not in assigned:
            assigned[arg.arg] = [ast.Dict(keys=[], values=[])]
    return assigned


def _module_functions(tree: ast.Module | None) -> dict[str, ast.expr]:
    """Every function defined in the file, by name.

    `return geom(data)` where `geom` builds the dict is the same defect as
    returning the dict literal; without resolving the call it classifies as
    "unknown" and slips through.
    """
    if tree is None:
        return {}
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _classify_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    functions: dict[str, ast.expr],
    depth: int,
) -> str:
    """Classify what a function returns, from its own return statements."""
    kinds = set()
    local = _local_assignments(func)
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            kinds.add(_classify_expr(node.value, local, depth + 1, functions))
    if not kinds:
        return "unknown"
    if "dict" in kinds:
        return "dict"
    return "str" if kinds == {"str"} else "unknown"


def _classify_string_call(call: ast.Call, name: str) -> str:
    """Classify a call from the `_STRING_CALLS` allowlist.

    `ElementTree.tostring` is the one member that does not always hand
    back a string: without `encoding="unicode"` it returns bytes, and a
    bytes payload reaches the artifact body as `b'<svg ...'` -- the same
    repr defect as a dict. So it only counts with that argument.
    """
    if name != "tostring":
        return "str"
    for keyword in call.keywords:
        if (
            keyword.arg == "encoding"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "unicode"
        ):
            return "str"
    return "unknown"


def _classify_expr(
    expr: ast.expr,
    assigned: dict[str, list[ast.expr]],
    depth: int = 0,
    functions: dict[str, ast.expr] | None = None,
) -> str:
    """Classify an expression as ``"dict"``, ``"str"`` or ``"unknown"``.

    Names are resolved back to their local assignments, so a dict built
    into a variable and then returned is still classified as a dict, and
    calls to functions defined in the same file are resolved to what those
    functions return.
    """
    functions = functions or {}
    if depth > 6:
        return "unknown"
    if isinstance(expr, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(expr, ast.Constant):
        return "str" if isinstance(expr.value, str) else "unknown"
    if isinstance(expr, ast.JoinedStr):
        return "str"
    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Name):
            if func.id == "dict":
                return "dict"
            # `str(x)` is classified by its argument. `str(a_dict)` is the
            # defect verbatim -- it is how the Python repr reaches the
            # artifact body -- not a compliant string return.
            if func.id in ("str", "format"):
                if expr.args:
                    inner = _classify_expr(expr.args[0], assigned, depth + 1, functions)
                    if inner == "dict":
                        return "dict"
                return "str"
            target = functions.get(func.id)
            if target is not None:
                return _classify_function(target, functions, depth)
            if func.id in _STRING_CALLS:
                return _classify_string_call(expr, func.id)
        if isinstance(func, ast.Attribute):
            # `.copy()` / `deepcopy()` hand back what they were given.
            if func.attr in ("copy", "deepcopy"):
                return _classify_expr(func.value, assigned, depth + 1, functions)
            # A function defined in this file outranks the allowlist.
            if func.attr not in functions and func.attr in _STRING_CALLS:
                return _classify_string_call(expr, func.attr)
            target = functions.get(func.attr)
            if target is not None:
                return _classify_function(target, functions, depth)
        return "unknown"
    if isinstance(expr, ast.BinOp):
        left = _classify_expr(expr.left, assigned, depth + 1, functions)
        right = _classify_expr(expr.right, assigned, depth + 1, functions)
        if "dict" in (left, right):
            return "dict"
        return "str" if "str" in (left, right) else "unknown"
    if isinstance(expr, ast.Name):
        kinds = {
            _classify_expr(value, assigned, depth + 1, functions)
            for value in assigned.get(expr.id, [])
        }
        if "dict" in kinds:
            return "dict"
        if kinds == {"str"}:
            return "str"
        return "unknown"
    if isinstance(expr, ast.IfExp):
        kinds = {
            _classify_expr(expr.body, assigned, depth + 1, functions),
            _classify_expr(expr.orelse, assigned, depth + 1, functions),
        }
        if "dict" in kinds:
            return "dict"
        return "str" if kinds == {"str"} else "unknown"
    return "unknown"


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """ids of the Constant nodes that are docstrings, not values."""
    out: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            out.add(id(first.value))
    return out


def _named_constants(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """Module-level and class-level assignments, by name.

    Covers both `TEMPLATE = "<svg ..."` used as a bare name and the same
    thing on a class, reached as `self.TEMPLATE`.
    """
    constants: dict[str, list[ast.expr]] = {}
    scopes: list[ast.Module | ast.ClassDef] = [tree]
    scopes += [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for scope in scopes:
        for node in scope.body:
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    constants.setdefault(target.id, []).append(node.value)
    return constants


def _reachable_nodes(tree: ast.Module | None) -> list[ast.AST]:
    """Every AST node the `transform` method can actually reach.

    Starts at the transform and follows calls to functions defined in the
    file and references to named constants, transitively. Scanning the
    whole module let markup that never reaches the output count as
    evidence: a module constant declared and never used passed the markup
    check for a transform whose body was `str({"width": 220})`.

    Reachability is resolved per scope, not per expression. Markup
    assembled across several statements of a helper still counts, which
    is how the examples in `python-transform.md` build it.
    """
    start = _find_transform_def(tree)
    if tree is None or start is None:
        return []
    functions = _module_functions(tree)
    constants = _named_constants(tree)

    out: list[ast.AST] = []
    seen: set[int] = set()
    queue: list[ast.AST] = [start]
    while queue:
        scope = queue.pop()
        if id(scope) in seen:
            continue
        seen.add(id(scope))
        for node in ast.walk(scope):
            out.append(node)
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            if name is None:
                continue
            target = functions.get(name)
            if target is not None:
                queue.append(target)
            queue.extend(constants.get(name, []))
    return out


def _string_literals(tree: ast.Module | None) -> list[str]:
    """String literals the `transform` method can actually reach.

    Docstrings are excluded: quoting `<svg xmlns=...>` in prose is
    evidence the markup appears in the file, not that it is built.
    """
    if tree is None:
        return []
    docstrings = _docstring_nodes(tree)
    out: list[str] = []
    for node in _reachable_nodes(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.extend(
                v.value
                for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
    return out


def check_artifact_content_type_declared(
    md_text: str = "", **_: Any
) -> tuple[bool, str]:
    """The artifact definition must declare a real content_type.

    All eight values are supported; the point of the check is that the
    non-text one is reachable and gets used when the output is a diagram.

    Only line-anchored declarations count, and every one of them is
    collected. A prose mention -- "not `content_type: text/plain`, the
    artifact IS a diagram" -- sits mid-sentence, so matching the first
    occurrence anywhere in the file failed answers that explained the
    choice before showing the registration.
    """
    declared = [
        match.group(1)
        for match in re.finditer(
            r"^[ \t]*-?[ \t]*content_type:\s*[\"']?([\w./+-]+)",
            md_text,
            re.MULTILINE,
        )
    ]
    if not declared:
        return False, "no content_type declared in the artifact definition"
    if "image/svg+xml" not in declared:
        return False, (
            f"content_type is {declared[0]!r}, expected image/svg+xml for a diagram"
        )
    return True, "content_type: image/svg+xml"


def check_svg_transform_returns_str(
    tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """A transform for a str-serialised content type must return a string.

    Only application/json and application/yaml turn a dict into structured
    output. Returning a dict for image/svg+xml stores `str(dict)` with no
    error, so the artifact looks populated and is a Python repr.

    A dict assembled into a local variable and then returned counts as a
    dict return: the returned name is resolved back to its assignments.
    So does `str(that_dict)` — wrapping the dict is how the repr reaches
    the body, not a way out of it. Passing needs every return to resolve
    to a string expression; the annotation is not evidence.
    """
    if tree is None:
        return False, "transform file missing or has a syntax error"

    func = _find_transform_def(tree)
    if func is None:
        return False, "no `transform` method found"

    returns = _transform_returns(tree)
    if not returns:
        return False, "no return statement found in the `transform` method"

    assigned = _local_assignments(func)
    functions = _module_functions(tree)
    kinds = [_classify_expr(expr, assigned, functions=functions) for expr in returns]
    if "dict" in kinds:
        return False, (
            "the transform's return resolves to a dict -- returned as-is "
            "or wrapped in str(); image/svg+xml is serialised with str(), "
            "so either way the body is a Python repr"
        )
    # A `-> str` annotation is a claim about the return, not the return.
    # Python does not enforce it, so `-> str` on a method that returns
    # `geom(data)` is exactly the defect this check exists to catch. What
    # counts is where the returned expression actually resolves.
    if all(kind == "str" for kind in kinds):
        annotated = isinstance(func.returns, ast.Name) and func.returns.id == "str"
        suffix = " and annotated -> str" if annotated else ""
        return True, f"every return resolves to a string expression{suffix}"
    return False, (
        "cannot show the transform returns a string: the returned "
        f"expression(s) resolve to {sorted(set(kinds))}. An `-> str` "
        "annotation is not evidence, because nothing enforces it"
    )


_SVG_ROOT_RE = re.compile(r"<svg\b", re.IGNORECASE)
_SVG_NS_RE = re.compile(r"xmlns\s*=\s*[\"']?http://www\.w3\.org/2000/svg")
_SVG_NS_URL_RE = re.compile(r"^http://www\.w3\.org/2000/svg$")
_ELEMENT_FACTORIES = frozenset({"Element", "SubElement", "makeelement", "fromstring"})


def _builds_svg_element(tree: ast.Module) -> bool:
    """True when the transform builds an `svg` root through ElementTree.

    `ET.Element("svg", {"xmlns": ...})` produces the same markup as an
    `<svg` literal; neither the tag nor the namespace appears in the
    literal spelling the text scan looks for. Scoped to reachable code
    for the same reason the literal scan is.
    """
    for node in _reachable_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in _ELEMENT_FACTORIES or not node.args:
            continue
        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
            and first.value.strip().lower().lstrip("<").startswith("svg")
        ):
            return True
    return False


def check_svg_markup_in_output(
    tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """The transform must actually build SVG markup.

    Independent of the return-shape check: a transform can return a
    string of the wrong thing -- a repr, a text table, a bare label --
    and still resolve to a string return. Helpers and named constants
    count, so this scans every literal the transform reaches rather than
    only the ones in its own body.

    Both signals are required, and each can be met by a text literal or
    by an ElementTree call -- `ET.Element("svg", {"xmlns": ...})` builds
    the same document without either spelling appearing as markup.
    """
    if tree is None:
        return False, "transform file missing or has a syntax error"
    reachable = _string_literals(tree)
    literals = "\n".join(reachable)
    missing: list[str] = []
    if not _SVG_ROOT_RE.search(literals) and not _builds_svg_element(tree):
        missing.append("an `<svg` root element")
    ns_declared = _SVG_NS_RE.search(literals) or any(
        _SVG_NS_URL_RE.match(value.strip()) for value in reachable
    )
    if not ns_declared:
        missing.append("the xmlns=http://www.w3.org/2000/svg namespace")
    if missing:
        return False, (
            f"no SVG markup built in the source: missing {' and '.join(missing)}"
        )
    return True, "builds SVG markup with an <svg root and the svg namespace"


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
    "watch-avoids-entry-directory": check_watch_avoids_entry_directory,
    "watch-empty-for-self-contained": check_watch_empty_for_self_contained,
    "watch-omitted-for-static-jinja2": check_watch_omitted_for_static_jinja2,
    "watch-declares-dynamic-jinja2-partials": check_watch_declares_dynamic_jinja2_partials,
    "artifact-content-type-declared": check_artifact_content_type_declared,
    "svg-transform-returns-str": check_svg_transform_returns_str,
    "svg-markup-in-output": check_svg_markup_in_output,
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
