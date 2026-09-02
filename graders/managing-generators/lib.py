"""Shared grader library for infrahub-managing-generators evaluations.

This library backs two grader families that share one ``run_checks`` entry
point, dispatched by the output file's suffix:

* **AST / relationship checks** (relationship references, multi-peer add,
  natural-key preflight) parse a Python source file the model produced as
  ``output.py``. Some expressions cannot be resolved from AST alone —
  variable references, function-call results — and the check functions treat
  those as "indeterminate" (passing) rather than failing. The checks fail
  only on shapes that are demonstrably wrong: bare string literals where a
  dict reference is required, over-packed list literals, list literals passed
  to ``.add()``. These checks take ``(tree, raw_text=...)``.

* **from_graphql hydration checks** parse a Markdown file (``output.md``)
  that carries the refactored generator and the updated cascade query as
  fenced ``python`` / ``graphql`` blocks. They verify the loop body does zero
  re-fetches (``InfrahubNode.from_graphql`` instead of ``self.client.get``)
  and that the query was extended with ``__typename``. These checks take a
  single ``output`` dict.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    # AST family — output.py
    result = run_checks(
        ["relationship-hfid-form-correct", "no-bare-string-relationship"],
        Path("output.py"),
    )

    # from_graphql family — output.md
    result = run_checks(
        ["imports-infrahub-node", "uses-from-graphql"],
        Path("output.md"),
    )
    print(result)  # {"score": 0.67, "details": "...", "checks": [...]}
"""

from __future__ import annotations

import ast
import re
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


_PY_FENCE = re.compile(
    r"^```(?:python|py)\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)
_GQL_FENCE = re.compile(
    r"^```(?:graphql|gql)\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)
_YAML_FENCE = re.compile(
    r"^```(?:yaml|yml)\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)


def load_output(path: Path) -> dict[str, str]:
    """Load the model's output.md and return its fenced blocks.

    Returns a dict with keys ``python``, ``python_all``, ``graphql``,
    ``yaml``, ``raw``. Missing blocks resolve to empty strings; ``raw`` is
    always the full file content (or "" if unreadable).

    ``python`` is the first ``python`` fence. ``python_all`` is every
    ``python`` fence that parses on its own, concatenated: an answer that
    presents a WRONG/RIGHT contrast, or splits the generator across two
    fences, must be graded on all of it rather than on whichever block
    happened to come first. Blocks that do not parse are dropped so one
    pseudo-code snippet cannot make the whole concatenation unparseable.
    """
    empty = {"python": "", "python_all": "", "graphql": "", "yaml": "", "raw": ""}
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return empty

    py_blocks = [m.group(1) for m in _PY_FENCE.finditer(raw)]
    parseable = [b for b in py_blocks if _parse_python(b) is not None]
    gql = _GQL_FENCE.search(raw)
    yaml_blocks = [m.group(1) for m in _YAML_FENCE.finditer(raw)]
    return {
        "python": py_blocks[0] if py_blocks else "",
        "python_all": "\n\n".join(parseable),
        "graphql": gql.group(1) if gql else "",
        "yaml": "\n".join(yaml_blocks),
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# AST helpers (relationship / multi-peer / preflight family)
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
# AST helpers (from_graphql hydration family)
# ---------------------------------------------------------------------------


def _parse_python(source: str) -> ast.Module | None:
    if not source.strip():
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _imports_infrahub_node(tree: ast.Module) -> bool:
    """True if `InfrahubNode` is imported (any infrahub_sdk path)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("infrahub_sdk"):
                if any(alias.name == "InfrahubNode" for alias in node.names):
                    return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name and "InfrahubNode" in alias.name:
                    return True
    return False


def _from_graphql_calls(tree: ast.Module) -> list[ast.Call]:
    """Return every `InfrahubNode.from_graphql(...)` call in the tree."""
    out: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "from_graphql":
            continue
        # Match `InfrahubNode.from_graphql` (Name) or `<x>.InfrahubNode.from_graphql`
        if isinstance(func.value, ast.Name) and func.value.id == "InfrahubNode":
            out.append(node)
        elif isinstance(func.value, ast.Attribute) and func.value.attr == "InfrahubNode":
            out.append(node)
    return out


def _client_get_calls(tree: ast.Module) -> list[ast.Call]:
    """Return every `self.client.get(...)` call in the tree."""
    out: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        val = func.value
        if not (isinstance(val, ast.Attribute) and val.attr == "client"):
            continue
        inner = val.value
        if isinstance(inner, ast.Name) and inner.id == "self":
            out.append(node)
    return out


def _node_within(child: ast.AST, parent: ast.AST) -> bool:
    """True if ``child`` is a descendant of ``parent`` in the AST."""
    for node in ast.walk(parent):
        if node is child:
            return True
    return False


def _for_loops(tree: ast.Module) -> list[ast.AST]:
    """Return every for / async-for loop in the tree."""
    return [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.For, ast.AsyncFor))
    ]


# ---------------------------------------------------------------------------
# Relationship field checks
# ---------------------------------------------------------------------------

# Relationship-like attribute names commonly used in this repo's base
# schema. The check inspects only these keys in the ``data=`` dict.
# Attribute-style scalar fields (name, status, description, etc.) are
# intentionally excluded so a bare ``"name": "x"`` doesn't fail.
#
# Maintenance note: this set is an allowlist of known base-schema
# relationship names. Generators referencing relationships outside this
# set (e.g. custom schema additions) will silently pass these checks
# even if shape is wrong. Extend this set when new relationship names
# enter the corpus, or invert to detect-by-value-shape if false
# negatives become a problem.
_RELATIONSHIP_KEYS = {
    "device_type", "manufacturer", "platform", "site", "location",
    "device", "interface", "connected_to", "endpoint_a", "endpoint_z",
    "role", "tenant", "provider", "circuit", "asn", "vlan", "vrf",
    "ip_namespace", "address", "prefix", "group",
}


def _is_known_relationship_key(key: str) -> bool:
    return key in _RELATIONSHIP_KEYS


def check_relationship_hfid_form_correct(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """For each relationship field in client.create(data=...), the value is
    one of: HFID dict, ID dict, or a Name/Attribute reference.

    Bare strings, list literals (non-HFID), or numeric literals fail.
    """
    if tree is None:
        return False, "No Python source to inspect"

    creates = find_client_create_calls(tree)
    if not creates:
        return False, "No self.client.create(...) calls found"

    problems: list[str] = []
    for call in creates:
        data_items = get_data_dict_items(call)
        for key, value in data_items.items():
            if not _is_known_relationship_key(key):
                continue
            hfid_ok, _elts = is_hfid_dict(value)
            if hfid_ok or is_id_dict(value) or is_name_or_attribute(value):
                continue
            problems.append(f"{key}: {ast.dump(value)[:60]}")

    if problems:
        return False, f"Wrong relationship reference shape: {'; '.join(problems)}"
    return True, "All relationship references use HFID dict, ID dict, or SDK object"


def check_no_bare_string_relationship(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """Relationship fields must not be bare string literals (bug 3 pattern)."""
    if tree is None:
        return False, "No Python source to inspect"

    creates = find_client_create_calls(tree)
    if not creates:
        return False, "No self.client.create(...) calls found"

    bad: list[str] = []
    for call in creates:
        for key, value in get_data_dict_items(call).items():
            if _is_known_relationship_key(key) and is_bare_string(value):
                bad.append(f"{key}={value.value!r}")

    if bad:
        return False, f"Bare-string relationship values (treated as id): {', '.join(bad)}"
    return True, "No bare-string relationship values found"


def check_no_overpacked_hfid_list(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """Single-component HFID targets must receive an HFID list of length 1.

    Heuristic: for the relationships that resolve to single-component HFIDs in
    Infrahub's base schema (DcimDeviceType, DcimPlatform, OrganizationManufacturer
    referenced via device_type/platform/manufacturer), the HFID list must be
    exactly one element."""
    SINGLE_COMPONENT_RELATIONSHIPS = {
        "device_type", "manufacturer", "platform", "site", "location",
        "role", "tenant", "provider",
    }

    if tree is None:
        return False, "No Python source to inspect"

    creates = find_client_create_calls(tree)
    if not creates:
        return False, "No self.client.create(...) calls found"

    bad: list[str] = []
    for call in creates:
        for key, value in get_data_dict_items(call).items():
            if key not in SINGLE_COMPONENT_RELATIONSHIPS:
                continue
            hfid_ok, elts = is_hfid_dict(value)
            if hfid_ok and elts is not None and len(elts) != 1:
                bad.append(f"{key} got HFID list of length {len(elts)} (expected 1)")

    if bad:
        return False, f"Over-packed HFID list: {', '.join(bad)}"
    return True, "No over-packed HFID lists for single-component targets"


def check_hfid_form_for_name_lookup(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """At least one relationship in client.create uses {"hfid": [...]}."""
    if tree is None:
        return False, "No Python source to inspect"
    for call in find_client_create_calls(tree):
        for key, value in get_data_dict_items(call).items():
            if _is_known_relationship_key(key):
                ok, _ = is_hfid_dict(value)
                if ok:
                    return True, f"{key} uses HFID dict form"
    return False, "No relationship uses {'hfid': [...]} form"


def check_id_form_for_uuid(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """At least one relationship in client.create uses {"id": ...}."""
    if tree is None:
        return False, "No Python source to inspect"
    for call in find_client_create_calls(tree):
        for key, value in get_data_dict_items(call).items():
            if _is_known_relationship_key(key) and is_id_dict(value):
                return True, f"{key} uses ID dict form"
    return False, "No relationship uses {'id': ...} form"


def check_sdk_object_reference_used(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """At least one relationship in client.create is a variable reference
    (presumably an SDK object from a prior client.get / client.create call).
    """
    if tree is None:
        return False, "No Python source to inspect"
    for call in find_client_create_calls(tree):
        for key, value in get_data_dict_items(call).items():
            if _is_known_relationship_key(key) and is_name_or_attribute(value):
                return True, f"{key} uses SDK object reference"
    return False, "No relationship passes an SDK object reference"


# ---------------------------------------------------------------------------
# Multi-peer add checks
# ---------------------------------------------------------------------------


def _is_list_referenced(node: ast.AST, tree: ast.Module) -> bool:
    """Best-effort: is ``node`` either a list literal or a Name that was
    assigned a list literal earlier in the module?
    """
    if isinstance(node, ast.List):
        return True
    if isinstance(node, ast.Name):
        target_name = node.id
        for assign in ast.walk(tree):
            if not isinstance(assign, ast.Assign):
                continue
            for tgt in assign.targets:
                if isinstance(tgt, ast.Name) and tgt.id == target_name:
                    if isinstance(assign.value, ast.List):
                        return True
                    if isinstance(assign.value, ast.ListComp):
                        return True
        # Also check ann-assigns: `devices: list[T] = [...]`
        for ann in ast.walk(tree):
            if not isinstance(ann, ast.AnnAssign):
                continue
            tgt = ann.target
            if isinstance(tgt, ast.Name) and tgt.id == target_name:
                if isinstance(ann.value, (ast.List, ast.ListComp)):
                    return True
    return False


def check_no_list_passed_to_add(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """No .add(...) call may receive a list argument as its sole peer."""
    if tree is None:
        return False, "No Python source to inspect"

    add_calls = find_relationship_add_calls(tree)
    if not add_calls:
        return False, "No .add(...) calls found"

    bad: list[str] = []
    for call in add_calls:
        if len(call.args) != 1:
            continue
        arg = call.args[0]
        if _is_list_referenced(arg, tree):
            bad.append(ast.unparse(call.func) if hasattr(ast, "unparse") else call.func.attr)

    if bad:
        return False, f".add() received a list: {', '.join(bad)}"
    return True, "No .add() call received a list argument"


def check_members_add_iterates(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """``.add(...)`` should appear inside a For loop OR be called multiple times
    on the same attribute path. Both indicate per-peer iteration.
    """
    if tree is None:
        return False, "No Python source to inspect"

    add_calls = find_relationship_add_calls(tree)
    if not add_calls:
        return False, "No .add(...) calls found"

    # Look for any For loop containing a .add() call
    for for_node in ast.walk(tree):
        if not isinstance(for_node, ast.For):
            continue
        for inner in ast.walk(for_node):
            if isinstance(inner, ast.Call) and inner in add_calls:
                return True, ".add() is called inside a for loop"

    # If multiple .add() calls share the same attribute path, treat as
    # explicit per-peer adds
    paths = []
    for call in add_calls:
        try:
            paths.append(ast.unparse(call.func))
        except Exception:
            pass
    if len(paths) >= 2 and len(set(paths)) < len(paths):
        return True, f".add() called multiple times: {len(add_calls)} calls"

    return False, "Only a single .add() call and not in a for loop"


# ---------------------------------------------------------------------------
# Natural-key preflight
# ---------------------------------------------------------------------------


def _has_save_with_upsert_true(tree: ast.Module) -> bool:
    """True if any ``.save(allow_upsert=True)`` call exists."""
    for call in _iter_calls(tree):
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "save":
            continue
        for kw in call.keywords:
            if kw.arg == "allow_upsert":
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return True
    return False


def _has_client_get_for_same_kind_as_create(tree: ast.Module) -> bool:
    """True if there is at least one ``client.get(kind=X)`` AND a
    ``client.create(kind=X)`` for the same kind value.
    """
    def _kind_arg(call: ast.Call) -> str | None:
        for kw in call.keywords:
            if kw.arg == "kind" and isinstance(kw.value, ast.Constant):
                return kw.value.value
        return None

    creates = find_client_create_calls(tree)
    gets = find_client_get_calls(tree)

    # Also accept generic ``client.get`` (not self.client.get) for non-generator scripts
    for call in _iter_calls(tree):
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "client":
            gets.append(call)

    # Also accept generic ``client.create`` for non-generator scripts
    for call in _iter_calls(tree):
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "create":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "client":
            creates.append(call)

    create_kinds = {_kind_arg(c) for c in creates if _kind_arg(c)}
    get_kinds = {_kind_arg(c) for c in gets if _kind_arg(c)}
    return bool(create_kinds & get_kinds)


def check_preflight_or_upsert(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """Either a same-kind client.get precedes create, OR save uses upsert."""
    if tree is None:
        return False, "No Python source to inspect"

    if _has_save_with_upsert_true(tree):
        return True, "save(allow_upsert=True) found"
    if _has_client_get_for_same_kind_as_create(tree):
        return True, "client.get preflights client.create for the same kind"
    return False, "Neither preflight client.get nor save(allow_upsert=True) found"


def check_no_raw_create_without_handler(
    tree: ast.Module | None, **_: Any
) -> tuple[bool, str]:
    """If client.create is used but neither preflight nor upsert is present,
    this is the bug 5 pattern.
    """
    if tree is None:
        return False, "No Python source to inspect"

    has_self_create = bool(find_client_create_calls(tree))
    has_bare_client_create = any(
        isinstance(c.func, ast.Attribute) and c.func.attr == "create"
        and isinstance(c.func.value, ast.Name) and c.func.value.id == "client"
        for c in _iter_calls(tree)
    )

    if not has_self_create and not has_bare_client_create:
        return False, "No client.create call found"

    if _has_save_with_upsert_true(tree):
        return True, "save(allow_upsert=True) covers the collision case"
    if _has_client_get_for_same_kind_as_create(tree):
        return True, "preflight client.get covers the collision case"
    return False, "client.create has no preflight and no allow_upsert=True"


# ---------------------------------------------------------------------------
# from_graphql hydration checks
#
# Each check has the signature:
#     check_*(output: dict[str, str], **kwargs) -> tuple[bool, str]
# where output is the dict returned by ``load_output``.
# ---------------------------------------------------------------------------


def check_imports_infrahub_node(output: dict, **_: Any) -> tuple[bool, str]:
    """Refactored Python imports InfrahubNode from infrahub_sdk."""
    tree = _parse_python(output["python"])
    if tree is None:
        return False, "No parseable Python block found"
    if _imports_infrahub_node(tree):
        return True, "InfrahubNode imported from infrahub_sdk"
    return False, "InfrahubNode is not imported from infrahub_sdk"


def check_uses_from_graphql(output: dict, **_: Any) -> tuple[bool, str]:
    """At least one InfrahubNode.from_graphql(...) call exists inside a for-loop."""
    tree = _parse_python(output["python"])
    if tree is None:
        return False, "No parseable Python block found"
    calls = _from_graphql_calls(tree)
    if not calls:
        return False, "No InfrahubNode.from_graphql(...) call found"
    loops = _for_loops(tree)
    in_loop = [c for c in calls if any(_node_within(c, loop) for loop in loops)]
    if not in_loop:
        return False, (
            f"InfrahubNode.from_graphql called {len(calls)}x but never "
            "inside a for-loop (expected inside the peer iteration)"
        )
    # Verify at least one call uses the expected kwargs.
    for call in in_loop:
        kwargs = {kw.arg for kw in call.keywords if kw.arg}
        if {"client", "data"}.issubset(kwargs):
            return True, (
                f"InfrahubNode.from_graphql called inside a for-loop "
                f"with client= and data= kwargs ({len(in_loop)} total)"
            )
    return False, (
        f"InfrahubNode.from_graphql called inside a for-loop but missing "
        "client= or data= kwargs"
    )


def check_no_client_get_in_loop(output: dict, **_: Any) -> tuple[bool, str]:
    """self.client.get(...) does not appear inside any for-loop body."""
    tree = _parse_python(output["python"])
    if tree is None:
        return False, "No parseable Python block found"
    get_calls = _client_get_calls(tree)
    loops = _for_loops(tree)
    leaked = [
        c for c in get_calls
        if any(_node_within(c, loop) for loop in loops)
    ]
    if leaked:
        return False, (
            f"self.client.get(...) still called inside a for-loop "
            f"({len(leaked)} occurrence(s)) — refactor incomplete"
        )
    return True, "No self.client.get(...) calls inside any for-loop"


def check_query_has_typename(output: dict, **_: Any) -> tuple[bool, str]:
    """The GraphQL query includes __typename inside the bgp_neighbors selection."""
    gql = output["graphql"]
    if not gql.strip():
        return False, "No GraphQL block found"
    # Locate bgp_neighbors { ... } block (allow nesting).
    match = re.search(r"bgp_neighbors\s*{", gql)
    if not match:
        return False, "bgp_neighbors selection not found in query"
    start = match.end()
    depth = 1
    end = start
    while end < len(gql) and depth > 0:
        if gql[end] == "{":
            depth += 1
        elif gql[end] == "}":
            depth -= 1
        end += 1
    block = gql[start:end]
    if "__typename" in block:
        return True, "__typename present inside bgp_neighbors selection"
    return False, "__typename missing from bgp_neighbors selection"


def check_python_block_present(output: dict, **_: Any) -> tuple[bool, str]:
    """A ```python fenced block exists in output.md."""
    if output["python"].strip():
        return True, "Python code block present"
    return False, "No ```python fenced block found in output.md"


def check_graphql_block_present(output: dict, **_: Any) -> tuple[bool, str]:
    """A ```graphql fenced block exists in output.md."""
    if output["graphql"].strip():
        return True, "GraphQL code block present"
    return False, "No ```graphql fenced block found in output.md"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Path traversal, shared-object ownership, group membership
#
# Verified against Infrahub 1.11.0 / SDK 1.23.1:
#   * `included_kinds` re-includes DEFAULT exclusions; the whitelist is
#     `kind_filter`, and neither stops the walk crossing a shared reference
#     object. Only `relationship_filter` does.
#   * `relationship_filter` takes schema identifiers, not relationship names.
#   * `save()` adds the node to the run's group unconditionally after the
#     create-or-update, so an upsert of a shared object claims it.
#   * `CoreGroup.members` peers `CoreNode`, which has no default_filter, so
#     membership cannot be resolved by name from the group side.
# ---------------------------------------------------------------------------


# The shared, low-cardinality object in the eval's scenario: reachable from
# every service target, so no single run may claim it.
_SHARED_KIND = "NetContainer"


def _answer_tree(output: dict) -> ast.Module | None:
    """Parse every python fence in the answer as one module.

    Grading only the first fence lets a WRONG/RIGHT contrast pair, or a
    generator split across two blocks, be judged on the wrong half.
    """
    return _parse_python(output.get("python_all") or output.get("python", ""))


def _calls_to(tree: ast.Module, methods: set[str]) -> list[ast.Call]:
    """Return every ``<expr>.<method>(...)`` call for the named methods."""
    return [
        c for c in _iter_calls(tree)
        if isinstance(c.func, ast.Attribute) and c.func.attr in methods
    ]


def _resolve_str_list(node: ast.AST, tree: ast.Module) -> tuple[bool, list[str]]:
    """Resolve ``node`` to a list of string constants.

    Follows one level of variable indirection so ``relationship_filter=RELS``
    is judged on what ``RELS`` holds. Returns ``(False, [])`` when the value
    cannot be determined, which callers treat as indeterminate rather than
    wrong.
    """
    if isinstance(node, ast.List):
        values = [
            e.value for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        return (True, values) if values else (False, [])
    if isinstance(node, ast.Name):
        for stmt in ast.walk(tree):
            if isinstance(stmt, ast.Assign):
                targets, value = stmt.targets, stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                targets, value = [stmt.target], stmt.value
            else:
                continue
            if value is None:
                continue
            for tgt in targets:
                if isinstance(tgt, ast.Name) and tgt.id == node.id:
                    if isinstance(value, ast.List):
                        return _resolve_str_list(value, tree)
    return False, []


def _kind_of_call(call: ast.Call) -> str | None:
    """Return the kind a create/get call targets, string or protocol class."""
    kind = get_kwarg(call, "kind")
    if isinstance(kind, ast.Constant) and isinstance(kind.value, str):
        return kind.value
    if isinstance(kind, ast.Name):
        return kind.id
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        if isinstance(first, ast.Name):
            return first.id
    return None


def _save_calls(tree: ast.Module) -> list[ast.Call]:
    return _calls_to(tree, {"save"})


def _save_opts_out(call: ast.Call) -> bool:
    """True if the save passes ``update_group_context=False``."""
    value = get_kwarg(call, "update_group_context")
    return isinstance(value, ast.Constant) and value.value is False


def _vars_bound_to_kind(tree: ast.Module, kind: str) -> set[str]:
    """Names assigned from a create/get of ``kind`` (``await`` unwrapped)."""
    names: set[str] = set()
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            targets, value = [stmt.target], stmt.value
        else:
            continue
        if isinstance(value, ast.Await):
            value = value.value
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        if not (isinstance(func, ast.Attribute) and func.attr in {"create", "get", "upsert"}):
            continue
        if _kind_of_call(value) != kind:
            continue
        for tgt in targets:
            if isinstance(tgt, ast.Name):
                names.add(tgt.id)
    return names


def _iterates_attribute(tree: ast.Module, attr: str) -> bool:
    """True if a for-loop or comprehension iterates over ``<expr>.<attr>``."""
    def _touches(node: ast.AST) -> bool:
        return any(
            isinstance(n, ast.Attribute) and n.attr == attr
            for n in ast.walk(node)
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor)) and _touches(node.iter):
            return True
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            if any(_touches(gen.iter) for gen in node.generators):
                return True
    return False


def check_traversal_uses_relationship_filter(
    output: dict, **_: Any
) -> tuple[bool, str]:
    """A traversal must be constrained by relationship identifier.

    Kind filtering restricts which nodes may appear, not which edges are
    followed, so a shared low-cardinality reference object still bridges
    unrelated subgraphs and the traversal returns structurally valid
    nonsense.

    Matched against the parsed call, not the raw text, so an explanatory
    comment cannot pass or fail the check on the model's behalf.
    """
    tree = _answer_tree(output)
    if tree is None:
        return False, "no parseable Python block found"

    calls = _calls_to(tree, {"traverse_paths", "path_exists"})
    if not calls:
        return False, "no traverse_paths / path_exists call found"

    for call in calls:
        if get_kwarg(call, "included_kinds") is not None:
            return False, (
                "passes included_kinds to the traversal; it only re-includes "
                "kinds excluded by default, so it is not a whitelist. The "
                "whitelist is kind_filter"
            )

    reasons: list[str] = []
    for call in calls:
        rel = get_kwarg(call, "relationship_filter")
        if rel is None:
            reasons.append(
                "a traversal call is not constrained by relationship_filter; "
                "kind filtering does not stop the walk crossing a shared node"
            )
            continue
        # A relationship identifier contains `__`; a per-side name does not.
        resolved, values = _resolve_str_list(rel, tree)
        if resolved and not any("__" in v for v in values):
            reasons.append(
                f"relationship_filter holds relationship names "
                f"({', '.join(values)}); it takes schema identifiers such as "
                "`device__interface`"
            )
            continue
        return True, "traversal constrained by relationship_filter"

    return False, "; ".join(reasons)


def check_traversal_enumerates_and_checks_truncation(
    output: dict, **_: Any
) -> tuple[bool, str]:
    """The traversal must enumerate the paths and check for truncation.

    The task needs one leg per discovered path. ``path_exists`` returns a
    bool, so it answers a different question and cannot enumerate anything;
    an answer built on it alone sidesteps the requirement. Once
    ``traverse_paths`` is used, ``truncated_at_depth`` is the only
    shape-level signal that the result is incomplete.
    """
    tree = _answer_tree(output)
    if tree is None:
        return False, "no parseable Python block found"

    if not _calls_to(tree, {"traverse_paths"}):
        if _calls_to(tree, {"path_exists"}):
            return False, (
                "only path_exists is used; it returns a bool, so it cannot "
                "enumerate the paths the task needs one leg per"
            )
        return False, "no traverse_paths call found"

    if not _iterates_attribute(tree, "paths"):
        return False, (
            "never iterates the returned .paths, so no leg is created per "
            "discovered path"
        )

    if not any(
        isinstance(n, ast.Attribute) and n.attr == "truncated_at_depth"
        for n in ast.walk(tree)
    ):
        return False, (
            "does not check truncated_at_depth, so a search that ran out of "
            "budget is treated as a complete answer"
        )
    return True, "enumerates .paths and checks truncated_at_depth"


def check_shared_save_opts_out_of_tracking(
    output: dict, **_: Any
) -> tuple[bool, str]:
    """Only the shared object's save may opt out of tracking.

    Every save() adds the node to the run's group, upserts included, so two
    targets both claim a shared object and whichever stops writing it
    deletes it. The opt-out is bound to that one save: applying it to every
    save disables the per-target cleanup the tracking group exists for.
    Creating the shared object outside the generator is the other accepted
    answer, so an answer that never writes it passes too.
    """
    tree = _answer_tree(output)
    if tree is None:
        return False, "no parseable Python block found"

    saves = _save_calls(tree)
    if not saves:
        return False, "no save() call found"

    opted_out = [c for c in saves if _save_opts_out(c)]
    if len(opted_out) == len(saves):
        return False, (
            f"every save() sets update_group_context=False, which opts the "
            f"whole run out of tracking and disables the per-target cleanup. "
            f"Only the shared {_SHARED_KIND} may opt out"
        )

    shared_vars = _vars_bound_to_kind(tree, _SHARED_KIND)
    if not shared_vars:
        return True, (
            f"the generator never creates the shared {_SHARED_KIND}, so the "
            "run cannot claim it (owned outside the generator)"
        )

    shared_saves = [
        c for c in saves
        if isinstance(c.func, ast.Attribute)
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id in shared_vars
    ]
    if not shared_saves:
        return True, (
            f"the shared {_SHARED_KIND} is referenced but never saved, so the "
            "run does not claim it"
        )

    if not all(_save_opts_out(c) for c in shared_saves):
        return False, (
            f"the shared {_SHARED_KIND} is saved without "
            "update_group_context=False; an upsert claims ownership just as a "
            "create does"
        )
    return True, f"the shared {_SHARED_KIND} is saved with update_group_context=False"


def check_group_membership_from_member_side(
    output: dict, **_: Any
) -> tuple[bool, str]:
    """Group membership in object data is written from the member side.

    `CoreGroup.members` peers `CoreNode`, which has no attributes and no
    default_filter, so a member name has nothing to resolve against.

    Read from the YAML fence only. Scanning the whole answer would let the
    prose that explains `member_of_groups` pass an object-data snippet that
    actually uses the group-side form.
    """
    yaml_block = output.get("yaml", "")
    if not yaml_block.strip():
        return False, "no ```yaml object-data block found"

    group_side = re.search(r"^\s*-?\s*members\s*:", yaml_block, re.M)
    member_side = re.search(r"^\s*-?\s*member_of_groups\s*:", yaml_block, re.M)

    if group_side:
        return False, (
            "the object data assigns membership from the group side via "
            "`members:`; the peer is CoreNode, which cannot be resolved by "
            "name. Use member_of_groups on each member"
        )
    if member_side:
        return True, "membership assigned from the member side"
    return False, "no group membership assignment found in the YAML block"


CHECKS: dict[str, Any] = {
    "traversal-uses-relationship-filter": check_traversal_uses_relationship_filter,
    "traversal-enumerates-and-checks-truncation": check_traversal_enumerates_and_checks_truncation,
    "shared-save-opts-out-of-tracking": check_shared_save_opts_out_of_tracking,
    "group-membership-from-member-side": check_group_membership_from_member_side,
    # AST / relationship family (output.py)
    "relationship-hfid-form-correct": check_relationship_hfid_form_correct,
    "no-bare-string-relationship": check_no_bare_string_relationship,
    "no-overpacked-hfid-list": check_no_overpacked_hfid_list,
    "hfid-form-for-name-lookup": check_hfid_form_for_name_lookup,
    "id-form-for-uuid": check_id_form_for_uuid,
    "sdk-object-reference-used": check_sdk_object_reference_used,
    "no-list-passed-to-add": check_no_list_passed_to_add,
    "members-add-iterates": check_members_add_iterates,
    "preflight-or-upsert": check_preflight_or_upsert,
    "no-raw-create-without-handler": check_no_raw_create_without_handler,
    # from_graphql hydration family (output.md)
    "imports-infrahub-node": check_imports_infrahub_node,
    "uses-from-graphql": check_uses_from_graphql,
    "no-client-get-in-loop": check_no_client_get_in_loop,
    "query-has-typename": check_query_has_typename,
    "python-block-present": check_python_block_present,
    "graphql-block-present": check_graphql_block_present,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against a generator-task output file.

    Dispatch is by the output file's suffix: ``.md`` routes to the
    Markdown/dict family (from_graphql hydration checks, which receive the
    ``load_output`` dict), anything else to the Python/AST family (which
    receive ``(tree, raw_text=...)`` from ``load_output_py``). A grader
    script requests only checks from its own family and passes the matching
    path, so the two never mix within one call.

    Returns skillgrade JSON: ``{"score": float, "details": str,
    "checks": [...]}``.

    Raises ``KeyError`` if any name in ``check_names`` is not in ``CHECKS``.
    """
    markdown_mode = Path(output_path).suffix.lower() == ".md"
    if markdown_mode:
        output = load_output(output_path)
    else:
        tree, raw = load_output_py(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            if markdown_mode:
                ok, msg = fn(output)
            else:
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
