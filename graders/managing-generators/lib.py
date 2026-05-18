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
    if len(paths) >= 2 and len(set(paths)) <= len(paths):
        return True, f".add() called multiple times: {len(add_calls)} calls"

    return False, "Only a single .add() call and not in a for loop"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "relationship-hfid-form-correct": check_relationship_hfid_form_correct,
    "no-bare-string-relationship": check_no_bare_string_relationship,
    "no-overpacked-hfid-list": check_no_overpacked_hfid_list,
    "hfid-form-for-name-lookup": check_hfid_form_for_name_lookup,
    "id-form-for-uuid": check_id_form_for_uuid,
    "sdk-object-reference-used": check_sdk_object_reference_used,
    "no-list-passed-to-add": check_no_list_passed_to_add,
    "members-add-iterates": check_members_add_iterates,
}


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
