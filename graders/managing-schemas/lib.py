"""Shared grader library for infrahub-managing-schemas skill evaluations.

Provides YAML parsing helpers, individual assertion check functions, a CHECKS
registry, and the top-level ``run_checks`` function that returns skillgrade
JSON format.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["schema-version", "attr-min-length", "dropdown-for-status"],
        Path("outputs/task-1/schema.yml"),
    )
    print(result)  # {"score": 0.67, "details": "...", "checks": [...]}
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# Low-level schema traversal helpers
# ---------------------------------------------------------------------------


def _all_nodes(schema: dict) -> list[dict]:
    """Return the list of node definitions from a schema dict."""
    return schema.get("nodes", []) or []


def _all_generics(schema: dict) -> list[dict]:
    """Return the list of generic definitions from a schema dict."""
    return schema.get("generics", []) or []


def _all_attrs(node: dict) -> list[dict]:
    """Return the attribute list for a single node or generic."""
    return node.get("attributes", []) or []


def _all_rels(node: dict) -> list[dict]:
    """Return the relationship list for a single node or generic."""
    return node.get("relationships", []) or []


def _full_kind(node: dict) -> str:
    """Return the full kind string (namespace + name) for a node or generic."""
    ns = node.get("namespace", "")
    name = node.get("name", "")
    return f"{ns}{name}"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output(path: Path) -> tuple[dict, str]:
    """Load a YAML schema file and return ``(parsed_dict, raw_text)``.

    If the file does not exist or cannot be parsed, returns ``({}, "")``.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}, ""

    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        parsed = {}

    return parsed, raw


# ---------------------------------------------------------------------------
# Individual check functions
#
# Each check has the signature:
#     check_*(schema: dict, **kwargs) -> tuple[bool, str]
#
# where the bool is True on pass, and str is a human-readable message.
# ---------------------------------------------------------------------------


def check_attr_min_length(schema: dict, **_: Any) -> tuple[bool, str]:
    """All attribute names must be >= 3 characters."""
    if not _all_nodes(schema) and not _all_generics(schema):
        return False, "No nodes or generics found"
    short: list[str] = []
    for node in _all_nodes(schema) + _all_generics(schema):
        for attr in _all_attrs(node):
            if len(attr.get("name", "")) < 3:
                short.append(f"{_full_kind(node)}.{attr['name']}")
    if short:
        return False, f"Short attribute names found: {', '.join(short)}"
    return True, "All attribute names >= 3 characters"


def check_dropdown_for_status(schema: dict, **_: Any) -> tuple[bool, str]:
    """Status attribute uses kind: Dropdown with choices."""
    for node in _all_nodes(schema):
        for attr in _all_attrs(node):
            if attr.get("name") == "status":
                if attr.get("kind") != "Dropdown":
                    return (
                        False,
                        f"{_full_kind(node)}.status uses kind: {attr.get('kind')}, expected Dropdown",
                    )
                if not attr.get("choices"):
                    return False, f"{_full_kind(node)}.status has no choices defined"
                return (
                    True,
                    f"{_full_kind(node)}.status uses Dropdown with {len(attr['choices'])} choices",
                )
    return False, "No status attribute found"


def check_no_deprecated_string(schema: dict, **_: Any) -> tuple[bool, str]:
    """No attribute should use the deprecated 'String' kind."""
    if not _all_nodes(schema) and not _all_generics(schema):
        return False, "No nodes or generics found"
    found: list[str] = []
    for node in _all_nodes(schema) + _all_generics(schema):
        for attr in _all_attrs(node):
            if attr.get("kind") == "String":
                found.append(f"{_full_kind(node)}.{attr['name']}")
    if found:
        return False, f"Deprecated 'String' kind used: {', '.join(found)}"
    return True, "All attributes use 'Text' (not deprecated 'String')"


def check_full_kind_references(schema: dict, **_: Any) -> tuple[bool, str]:
    """All peer references use full Namespace+Name kind."""
    all_items = _all_nodes(schema) + _all_generics(schema)
    all_rels = [rel for node in all_items for rel in _all_rels(node)]
    if not all_rels:
        return False, "No relationships found"
    defined_kinds = {_full_kind(n) for n in all_items}
    names_only = {n.get("name", "") for n in all_items}

    short: list[str] = []
    for node in all_items:
        for rel in _all_rels(node):
            peer = rel.get("peer", "")
            if not peer:
                continue
            # Skip well-known external kinds
            if peer.startswith("Builtin") or peer.startswith("Infra"):
                continue
            # A peer is "short" if it matches a node name but not the full kind
            if peer in names_only and peer not in defined_kinds:
                short.append(f"{_full_kind(node)}.{rel['name']} -> {peer}")
    if short:
        return False, f"Short peer references: {', '.join(short)}"
    return True, "All peer references use full Namespace+Name kind"


def check_human_friendly_id(schema: dict, **_: Any) -> tuple[bool, str]:
    """human_friendly_id is defined on all nodes (or inherited from a generic)."""
    if not _all_nodes(schema):
        return False, "No nodes found"
    missing: list[str] = []
    for node in _all_nodes(schema):
        if not node.get("human_friendly_id"):
            # Check if inherited from a generic that has human_friendly_id
            inherits = node.get("inherit_from", []) or []
            if inherits:
                for generic in _all_generics(schema):
                    if _full_kind(generic) in inherits and generic.get("human_friendly_id"):
                        break  # found it in the generic
                else:
                    missing.append(_full_kind(node))
            else:
                missing.append(_full_kind(node))
    if missing:
        return False, f"Missing human_friendly_id: {', '.join(missing)}"
    return True, "human_friendly_id defined on all nodes"


def check_display_label_singular(schema: dict, **_: Any) -> tuple[bool, str]:
    """Uses display_label (singular), not deprecated display_labels (plural)."""
    bad: list[str] = []
    for node in _all_nodes(schema) + _all_generics(schema):
        if "display_labels" in node:
            bad.append(_full_kind(node))
    if bad:
        return False, f"Deprecated display_labels (plural) found on: {', '.join(bad)}"
    # Check at least one node or generic has display_label
    has_label = any(
        "display_label" in n
        for n in _all_nodes(schema) + _all_generics(schema)
    )
    if not has_label:
        return False, "No display_label found on any node or generic"
    return True, "Uses display_label (singular Jinja2 string)"


def check_schema_version(schema: dict, **_: Any) -> tuple[bool, str]:
    """Schema starts with version: '1.0'."""
    version = schema.get("version")
    if version == "1.0":
        return True, "version: '1.0'"
    return False, f"version is '{version}', expected '1.0'"


def check_matching_identifiers(schema: dict, **_: Any) -> tuple[bool, str]:
    """All relationship identifier pairs match between both sides."""
    all_items = _all_nodes(schema) + _all_generics(schema)
    all_rels = [rel for node in all_items for rel in _all_rels(node)]
    if not all_rels:
        return False, "No relationships found"

    # Build a map of identifier -> list of (node_kind, rel_name, peer)
    id_map: dict[str, list[tuple[str, str, str]]] = {}
    for node in all_items:
        for rel in _all_rels(node):
            ident = rel.get("identifier")
            if ident:
                id_map.setdefault(ident, []).append(
                    (_full_kind(node), rel.get("name", ""), rel.get("peer", ""))
                )

    defined_kinds = {_full_kind(n) for n in all_items}

    # Each identifier should appear at least twice (both sides) unless the
    # peer is an external kind not defined in this schema.
    orphans: list[str] = []
    for ident, usages in id_map.items():
        if len(usages) >= 2:
            continue
        # Single usage — check if the peer is external
        peer = usages[0][2]
        if peer not in defined_kinds:
            continue  # External peer; skip
        orphans.append(f"{ident} (only on {usages[0][0]}.{usages[0][1]})")

    if orphans:
        return False, f"Orphan identifiers (only one side defined): {', '.join(orphans)}"
    return True, "All relationship identifiers match between both sides"


def check_hierarchical_generic(schema: dict, **_: Any) -> tuple[bool, str]:
    """A generic is defined with hierarchical: true."""
    for generic in _all_generics(schema):
        if generic.get("hierarchical") is True:
            return True, f"{_full_kind(generic)} has hierarchical: true"
    return False, "No generic with hierarchical: true found"


def check_inherit_from_generic(schema: dict, **_: Any) -> tuple[bool, str]:
    """All nodes inherit_from the hierarchical generic using its full kind."""
    hier_kind: str | None = None
    for generic in _all_generics(schema):
        if generic.get("hierarchical") is True:
            hier_kind = _full_kind(generic)
            break
    if not hier_kind:
        return False, "No hierarchical generic found"

    missing: list[str] = []
    for node in _all_nodes(schema):
        inherits = node.get("inherit_from", []) or []
        if hier_kind not in inherits:
            missing.append(_full_kind(node))
    if missing:
        return False, f"Nodes not inheriting from {hier_kind}: {', '.join(missing)}"
    return True, f"All nodes inherit from {hier_kind}"


def check_root_no_parent(schema: dict, **_: Any) -> tuple[bool, str]:
    """Root node has parent set to empty string or null."""
    for node in _all_nodes(schema):
        parent = node.get("parent")
        if parent is None or parent == "" or parent == "null":
            return True, f"{_full_kind(node)} has parent: {repr(parent)}"
    return False, "No root node with parent null or empty string found"


def check_correct_hierarchy_chain(schema: dict, **_: Any) -> tuple[bool, str]:
    """Parent/children chain: Region->Site->Room->Rack."""
    nodes_by_name: dict[str, dict] = {}
    for node in _all_nodes(schema):
        name_lower = node.get("name", "").lower()
        nodes_by_name[name_lower] = node

    expected = [("region", "site"), ("site", "room"), ("room", "rack")]
    issues: list[str] = []
    for parent_name, child_name in expected:
        parent_node = nodes_by_name.get(parent_name)
        child_node = nodes_by_name.get(child_name)
        if not parent_node:
            issues.append(f"Node '{parent_name}' not found")
            continue
        if not child_node:
            issues.append(f"Node '{child_name}' not found")
            continue

        children_val = parent_node.get("children", "")
        child_kind = _full_kind(child_node)
        if children_val:
            if isinstance(children_val, list):
                children_tokens = [str(v) for v in children_val]
            else:
                children_tokens = [str(children_val)]
            if child_kind not in children_tokens:
                issues.append(
                    f"{_full_kind(parent_node)}.children does not reference {child_kind}"
                )

        parent_val = child_node.get("parent", "")
        parent_kind = _full_kind(parent_node)
        if parent_val:
            if isinstance(parent_val, list):
                parent_tokens = [str(v) for v in parent_val]
            else:
                parent_tokens = [str(parent_val)]
            if parent_kind not in parent_tokens:
                issues.append(
                    f"{_full_kind(child_node)}.parent does not reference {parent_kind}"
                )

    if issues:
        return False, "; ".join(issues)
    return True, "Region->Site->Room->Rack hierarchy is correct"


def check_two_endpoint_relationships(schema: dict, **_: Any) -> tuple[bool, str]:
    """Circuit has two endpoint relationships (side_a/side_z)."""
    for node in _all_nodes(schema):
        if node.get("name", "").lower() == "circuit":
            endpoint_rels = [
                rel.get("name")
                for rel in _all_rels(node)
                if "endpoint" in rel.get("name", "").lower() or "side" in rel.get("name", "").lower()
            ]
            if len(endpoint_rels) >= 2:
                return (
                    True,
                    f"Circuit has {len(endpoint_rels)} endpoint relationships: {', '.join(endpoint_rels)}",
                )
            elif len(endpoint_rels) == 1:
                return (
                    False,
                    f"Circuit has only 1 endpoint relationship: {endpoint_rels[0]} (expected 2 for side_a/side_z)",
                )
            else:
                return False, "Circuit has no endpoint relationships"
    return False, "No Circuit node found"


def check_attribute_kind_relationships(schema: dict, **_: Any) -> tuple[bool, str]:
    """Circuit-to-Provider uses kind: Attribute with matching identifiers."""
    for node in _all_nodes(schema):
        if node.get("name", "").lower() == "circuit":
            for rel in _all_rels(node):
                peer = rel.get("peer", "").lower()
                if "provider" in peer:
                    kind = rel.get("kind")
                    if kind == "Attribute":
                        return True, f"Circuit.{rel['name']} -> {rel['peer']} uses kind: Attribute"
                    return (
                        False,
                        f"Circuit.{rel['name']} -> {rel['peer']} uses kind: {kind}, expected Attribute",
                    )
    return False, "No Circuit-to-Provider relationship found"


def check_endpoint_device_relationship(schema: dict, **_: Any) -> tuple[bool, str]:
    """CircuitEndpoint-to-Device uses kind: Attribute with matching identifiers."""
    for node in _all_nodes(schema):
        name = node.get("name", "").lower()
        if "endpoint" in name:
            for rel in _all_rels(node):
                rel_name = rel.get("name", "").lower()
                rel_peer = rel.get("peer", "").lower()
                if "device" in rel_name or "device" in rel_peer:
                    kind = rel.get("kind")
                    if kind == "Attribute":
                        return True, f"{_full_kind(node)}.{rel['name']} uses kind: Attribute"
                    return (
                        False,
                        f"{_full_kind(node)}.{rel['name']} uses kind: {kind}, expected Attribute",
                    )
    return False, "No Endpoint-to-Device relationship found"


def check_parent_rel_optional_false(schema: dict, **_: Any) -> tuple[bool, str]:
    """Every relationship with kind: Parent must have optional: false and cardinality: one.

    Server-validated by `_validate_parents_one_schema` — the schema fails to
    load if a Parent relationship is optional or has cardinality != one.
    """
    all_items = _all_nodes(schema) + _all_generics(schema)
    bad: list[str] = []
    found_any = False
    for node in all_items:
        for rel in _all_rels(node):
            if rel.get("kind") != "Parent":
                continue
            found_any = True
            ref = f"{_full_kind(node)}.{rel.get('name', '')}"
            if rel.get("optional", True) is not False:
                bad.append(f"{ref} missing optional: false")
            if rel.get("cardinality") != "one":
                bad.append(f"{ref} cardinality is {rel.get('cardinality')!r}, expected 'one'")
    if not found_any:
        return False, "No kind: Parent relationship found"
    if bad:
        return False, "; ".join(bad)
    return True, "All kind: Parent relationships have optional: false and cardinality: one"


def check_parent_rel_single(schema: dict, **_: Any) -> tuple[bool, str]:
    """Each node has at most one relationship with kind: Parent."""
    all_items = _all_nodes(schema) + _all_generics(schema)
    bad: list[str] = []
    for node in all_items:
        parents = [rel for rel in _all_rels(node) if rel.get("kind") == "Parent"]
        if len(parents) > 1:
            names = ", ".join(p.get("name", "?") for p in parents)
            bad.append(f"{_full_kind(node)} has {len(parents)} Parent rels: {names}")
    if bad:
        return False, "; ".join(bad)
    return True, "Every node has at most one kind: Parent relationship"


def check_computed_jinja2_readonly(schema: dict, **_: Any) -> tuple[bool, str]:
    """Every attribute with computed_attribute must have read_only: true.

    Required pairing — the system populates the value on every save, so
    user writes must be blocked. Infrahub validates this at schema load.
    """
    all_items = _all_nodes(schema) + _all_generics(schema)
    bad: list[str] = []
    found_any = False
    for node in all_items:
        for attr in _all_attrs(node):
            if "computed_attribute" not in attr:
                continue
            found_any = True
            ref = f"{_full_kind(node)}.{attr.get('name', '')}"
            if attr.get("read_only") is not True:
                bad.append(f"{ref} missing read_only: true")
    if not found_any:
        return False, "No computed_attribute found"
    if bad:
        return False, "; ".join(bad)
    return True, "All computed_attribute fields have read_only: true"


def check_computed_jinja2_kind(schema: dict, **_: Any) -> tuple[bool, str]:
    """Every computed_attribute uses kind: Jinja2 with a non-empty template."""
    all_items = _all_nodes(schema) + _all_generics(schema)
    bad: list[str] = []
    found_any = False
    for node in all_items:
        for attr in _all_attrs(node):
            comp = attr.get("computed_attribute")
            if not comp:
                continue
            found_any = True
            ref = f"{_full_kind(node)}.{attr.get('name', '')}"
            if comp.get("kind") != "Jinja2":
                bad.append(f"{ref} computed_attribute.kind is {comp.get('kind')!r}, expected 'Jinja2'")
            if not comp.get("jinja2_template"):
                bad.append(f"{ref} missing jinja2_template")
    if not found_any:
        return False, "No computed_attribute found"
    if bad:
        return False, "; ".join(bad)
    return True, "All computed_attribute entries use kind: Jinja2 with a template"


def check_on_delete_cascade_present(schema: dict, **_: Any) -> tuple[bool, str]:
    """At least one relationship sets on_delete: cascade.

    Used in evals where the prompt describes owned children whose existence
    has no meaning without the parent. Cascade is opt-in; defaults to
    no-action.
    """
    all_items = _all_nodes(schema) + _all_generics(schema)
    cascading: list[str] = []
    for node in all_items:
        for rel in _all_rels(node):
            if rel.get("on_delete") == "cascade":
                cascading.append(f"{_full_kind(node)}.{rel.get('name', '')}")
    if cascading:
        return True, f"Found cascade on: {', '.join(cascading)}"
    return False, "No relationship sets on_delete: cascade"


def check_generate_template_concrete_only(schema: dict, **_: Any) -> tuple[bool, str]:
    """generate_template: true must only appear on concrete nodes, never generics.

    Generics are not instantiable, so the Object Template clone UX is
    meaningless on them.
    """
    bad_generics: list[str] = []
    for generic in _all_generics(schema):
        if generic.get("generate_template") is True:
            bad_generics.append(_full_kind(generic))
    if bad_generics:
        return False, f"generate_template: true on generics: {', '.join(bad_generics)}"

    flagged_nodes = [
        _full_kind(node) for node in _all_nodes(schema) if node.get("generate_template") is True
    ]
    if not flagged_nodes:
        return False, "No node sets generate_template: true"
    return True, f"generate_template: true on concrete nodes only: {', '.join(flagged_nodes)}"


def check_generate_profile_concrete_only(schema: dict, **_: Any) -> tuple[bool, str]:
    """generate_profile: true must appear on concrete nodes, never generics.

    Profiles generate a companion Profile<Kind> for an instantiable node;
    generics are not instantiable, so the flag is meaningless on them.
    """
    bad_generics = [
        _full_kind(g) for g in _all_generics(schema) if g.get("generate_profile") is True
    ]
    if bad_generics:
        return False, f"generate_profile: true on generics: {', '.join(bad_generics)}"

    flagged = [
        _full_kind(n) for n in _all_nodes(schema) if n.get("generate_profile") is True
    ]
    if not flagged:
        return False, "No node sets generate_profile: true"
    return True, f"generate_profile: true on concrete nodes only: {', '.join(flagged)}"


_FETCH_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "infrahub-managing-schemas"
    / "scripts"
    / "fetch_schema_limits.py"
)
_SCHEMA_LIMITS_CACHE: dict[str, dict[str, int]] | None = None
_SCHEMA_LIMITS_ERROR: str | None = None
_SCHEMA_NAMES = ("NodeSchema", "GenericSchema",
                 "AttributeSchema", "RelationshipSchema")


def _load_schema_limits() -> tuple[dict[str, dict[str, int]] | None, str | None]:
    """Run the shared fetch script and return per-schema maxLength tables.

    Caches the result for the lifetime of the process. On any failure
    (script missing, non-zero exit, malformed JSON) limits are ``None``
    and an error string is returned for the caller to surface.
    """
    global _SCHEMA_LIMITS_CACHE, _SCHEMA_LIMITS_ERROR
    if _SCHEMA_LIMITS_CACHE is not None:
        return _SCHEMA_LIMITS_CACHE, None
    if _SCHEMA_LIMITS_ERROR is not None:
        return None, _SCHEMA_LIMITS_ERROR

    import json
    import subprocess
    import sys

    if not _FETCH_SCRIPT.is_file():
        _SCHEMA_LIMITS_ERROR = f"fetch script not found at {_FETCH_SCRIPT}"
        return None, _SCHEMA_LIMITS_ERROR

    try:
        proc = subprocess.run(
            [sys.executable, str(_FETCH_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _SCHEMA_LIMITS_ERROR = f"{type(exc).__name__}: {exc}"
        return None, _SCHEMA_LIMITS_ERROR

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip().splitlines()[-1:] or ["non-zero exit"]
        _SCHEMA_LIMITS_ERROR = f"exit {proc.returncode}: {stderr[0]}"
        return None, _SCHEMA_LIMITS_ERROR

    try:
        full = json.loads(proc.stdout)
    except ValueError as exc:
        _SCHEMA_LIMITS_ERROR = f"invalid JSON from fetch script: {exc}"
        return None, _SCHEMA_LIMITS_ERROR

    # Project {SchemaName: {field: {minLength, maxLength, pattern}}}
    # down to {SchemaName: {field: maxLength}} for the cap-only check.
    limits: dict[str, dict[str, int]] = {}
    for name in _SCHEMA_NAMES:
        limits[name] = {
            field: info["maxLength"]
            for field, info in full.get(name, {}).items()
            if "maxLength" in info
        }
    _SCHEMA_LIMITS_CACHE = limits
    return limits, None


def check_string_limits(schema: dict, **_: Any) -> tuple[bool, str]:
    """All schema string fields fit Infrahub's load-time max_length caps.

    Delegates to ``skills/infrahub-managing-schemas/scripts/fetch_schema_limits.py``
    so the source-of-truth URL and extraction logic live in exactly one
    place across the repo. If the script can't reach the live schema,
    the check returns ``True`` with an explicit "unverified" reason so
    transient network failures don't fail CI — the result is visibly
    inconclusive.
    """
    limits, error = _load_schema_limits()
    if limits is None:
        return True, (
            f"String-length caps not verified — fetch_schema_limits.py failed "
            f"({error}). Check skipped for this run."
        )

    def _check(ref: str, obj: dict, table: dict[str, int], issues: list[str]) -> None:
        for field, cap in table.items():
            value = obj.get(field)
            if isinstance(value, str) and len(value) > cap:
                issues.append(f"{ref}.{field}={len(value)} (max {cap})")

    issues: list[str] = []
    for node in _all_nodes(schema):
        ref = _full_kind(node) or "<unnamed>"
        _check(ref, node, limits["NodeSchema"], issues)
        for attr in _all_attrs(node):
            _check(f"{ref}.{attr.get('name', '?')}", attr, limits["AttributeSchema"], issues)
        for rel in _all_rels(node):
            _check(f"{ref}.{rel.get('name', '?')}", rel, limits["RelationshipSchema"], issues)
    for generic in _all_generics(schema):
        ref = _full_kind(generic) or "<unnamed>"
        _check(ref, generic, limits["GenericSchema"], issues)
        for attr in _all_attrs(generic):
            _check(f"{ref}.{attr.get('name', '?')}", attr, limits["AttributeSchema"], issues)
        for rel in _all_rels(generic):
            _check(f"{ref}.{rel.get('name', '?')}", rel, limits["RelationshipSchema"], issues)

    if issues:
        return False, "Over-limit string fields: " + "; ".join(issues)
    return True, "All string fields within max_length caps (per fetch_schema_limits.py)"


def check_core_artifact_target_concrete(schema: dict, **_: Any) -> tuple[bool, str]:
    """CoreArtifactTarget is inherited only by concrete nodes, not by generics.

    Generics cannot be artifact targets — artifacts attach to instances.
    """
    bad_generics: list[str] = []
    for generic in _all_generics(schema):
        inherits = generic.get("inherit_from", []) or []
        if "CoreArtifactTarget" in inherits:
            bad_generics.append(_full_kind(generic))
    if bad_generics:
        return False, f"CoreArtifactTarget on generics: {', '.join(bad_generics)}"

    inheriting_nodes = [
        _full_kind(node)
        for node in _all_nodes(schema)
        if "CoreArtifactTarget" in (node.get("inherit_from", []) or [])
    ]
    if not inheriting_nodes:
        return False, "No node inherits from CoreArtifactTarget"
    return True, f"CoreArtifactTarget inherited by concrete nodes only: {', '.join(inheriting_nodes)}"


_CORE_FILE_OBJECT_RESERVED_ATTRS = {
    "file_name",
    "file_size",
    "file_type",
    "checksum",
    "storage_id",
}

_FILE_BYPASS_TEXT_ATTR_NAMES = {
    "file_url",
    "file_path",
    "file_name",
    "filename",
    "url",
    "path",
    "location",
}


def _nodes_inheriting_core_file_object(schema: dict) -> list[dict]:
    return [
        node
        for node in _all_nodes(schema)
        if "CoreFileObject" in (node.get("inherit_from", []) or [])
    ]


def check_core_file_object_inherited(schema: dict, **_: Any) -> tuple[bool, str]:
    """At least one concrete node inherits from CoreFileObject."""
    inheriting = [_full_kind(node) for node in _nodes_inheriting_core_file_object(schema)]
    if not inheriting:
        return False, "No node inherits from CoreFileObject"
    return True, f"CoreFileObject inherited by: {', '.join(inheriting)}"


def check_file_object_on_node_not_generic(schema: dict, **_: Any) -> tuple[bool, str]:
    """CoreFileObject is inherited only by concrete nodes, not by generics.

    Generics aren't instantiable — files have nothing to upload to.
    """
    bad_generics = [
        _full_kind(generic)
        for generic in _all_generics(schema)
        if "CoreFileObject" in (generic.get("inherit_from", []) or [])
    ]
    if bad_generics:
        return False, f"CoreFileObject on generics: {', '.join(bad_generics)}"
    return True, "CoreFileObject not declared on any generic"


def check_no_reserved_file_attrs(schema: dict, **_: Any) -> tuple[bool, str]:
    """Nodes inheriting CoreFileObject must not redeclare reserved attributes.

    file_name, file_size, file_type, checksum, storage_id are system-managed
    and read-only; redeclaring collides with inherited definitions.
    """
    violations: list[str] = []
    for node in _nodes_inheriting_core_file_object(schema):
        kind = _full_kind(node)
        for attr in _all_attrs(node):
            name = attr.get("name")
            if name in _CORE_FILE_OBJECT_RESERVED_ATTRS:
                violations.append(f"{kind}.{name}")
    if violations:
        return False, (
            "Reserved CoreFileObject attributes redeclared: "
            + ", ".join(violations)
        )
    return True, "No reserved CoreFileObject attributes redeclared"


def check_no_filename_text_bypass(schema: dict, **_: Any) -> tuple[bool, str]:
    """Nodes inheriting CoreFileObject must not also store a path/URL Text attr.

    A Text attribute named url/path/file_url/file_path/filename/location on a
    CoreFileObject heir is the bypass antipattern — the file should live in
    object storage, not be a string pointer alongside it.
    """
    violations: list[str] = []
    for node in _nodes_inheriting_core_file_object(schema):
        kind = _full_kind(node)
        for attr in _all_attrs(node):
            name = attr.get("name")
            if (
                name in _FILE_BYPASS_TEXT_ATTR_NAMES
                and attr.get("kind") == "Text"
                and name not in _CORE_FILE_OBJECT_RESERVED_ATTRS
            ):
                violations.append(f"{kind}.{name}")
    if violations:
        return False, (
            "Text attributes that bypass CoreFileObject storage: "
            + ", ".join(violations)
        )
    return True, "No bypass Text attributes alongside CoreFileObject inheritance"


# ---------------------------------------------------------------------------
# Branch-first workflow checks (text-based)
#
# The branch-first task produces a rollout *plan* (Markdown / commands), not a
# schema YAML, so these inspect ``raw_text`` rather than the parsed ``schema``.
# Patterns are intentionally duplicated from graders/managing-objects/lib.py —
# the skills' graders are independently owned, so we copy rather than hoist.
# ---------------------------------------------------------------------------


# The change should be scoped to a dedicated branch. Any of these is a strong
# signal the plan keeps the write off the default branch: an explicit
# `--branch` flag, an `infrahubctl branch create` step, or prose that puts the
# work on a branch.
_BRANCH_PATTERNS = [
    re.compile(r"--branch\b", re.IGNORECASE),
    re.compile(r"\bbranch\s+create\b", re.IGNORECASE),
    re.compile(r"\bcreate\s+(?:a\s+)?(?:new\s+)?branch\b", re.IGNORECASE),
    re.compile(r"\b(?:on|onto|to|use|using|in|via|a)\s+(?:a\s+)?(?:new\s+|named\s+|feature\s+|separate\s+)?branch\b", re.IGNORECASE),
    re.compile(r"\bbranch[-_]?(?:name|first)\b", re.IGNORECASE),
]


def check_recommends_branch(schema: dict, *, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Fail if the plan does not scope the schema change to a branch."""
    for pat in _BRANCH_PATTERNS:
        if pat.search(raw_text):
            return True, f"Recommends a branch (matched {pat.pattern!r})"
    return False, "Does not recommend applying the schema change on a branch"


# The plan should make clear the dedicated branch is the safe alternative to
# the default branch: cautioning against loading straight to the default
# branch (named generically, or by its conventional name `main`), routing
# through the proposed-change / merge review path, or noting the branch is
# discardable.
_DEFAULT_BRANCH_RISK_PATTERNS = [
    re.compile(r"\b(?:not|instead of|rather than|avoid|without|never|off)\b[^.\n]{0,40}\bdefault\s+branch\b", re.IGNORECASE),
    re.compile(r"\b(?:directly|straight)\s+(?:in)?to\s+(?:the\s+)?default\s+branch\b", re.IGNORECASE),
    re.compile(r"\b(?:not|instead of|rather than|avoid|without|never|off)\b[^.\n]{0,40}\bmain\b", re.IGNORECASE),
    re.compile(r"\b(?:directly|straight)\s+(?:in)?to\s+(?:the\s+)?`?main`?\b", re.IGNORECASE),
    re.compile(r"\bproposed[-\s]?change\b", re.IGNORECASE),
    re.compile(r"\bmerge\b", re.IGNORECASE),
    re.compile(r"\bdiscard\b", re.IGNORECASE),
    re.compile(r"\bthrow\s+(?:it\s+)?away\b", re.IGNORECASE),
    re.compile(r"\b(?:delete|drop)\s+the\s+branch\b", re.IGNORECASE),
]


def check_explains_default_branch_risk_or_review(schema: dict, *, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Fail if the plan neither warns about the default branch nor routes through review."""
    for pat in _DEFAULT_BRANCH_RISK_PATTERNS:
        if pat.search(raw_text):
            return True, f"Explains default-branch risk / review path (matched {pat.pattern!r})"
    return False, "Does not caution against the default branch or mention the review/merge/discard path"


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

def check_inverse_reuses_forward_identifier(schema: dict, **_: Any) -> tuple[bool, str]:
    """The added inverse reuses the pre-existing forward identifier verbatim.

    The task seeds an existing forward relationship whose identifier is the
    auto-generated-looking ``dcimdevice__dciminterface``. Adding the inverse
    must reuse that exact string on both sides. Inventing a fresh identifier
    (e.g. ``device__interfaces``) and renaming the forward side to match is
    the antipattern this check guards against — a rename fails on a live
    instance with ``not_supported`` because the identifier is immutable.
    ``check_matching_identifiers`` cannot catch it: it passes as long as both
    sides agree, even when both were renamed to an invented value.
    """
    expected = "dcimdevice__dciminterface"
    all_items = _all_nodes(schema) + _all_generics(schema)

    link_idents: set[str] = set()
    inverse_found = False
    for node in all_items:
        for rel in _all_rels(node):
            peer = rel.get("peer", "")
            name = rel.get("name", "")
            # Relationships that form the Device <-> Interface link.
            if peer.startswith("Dcim") and ("Device" in peer or "Interface" in peer):
                ident = rel.get("identifier")
                if ident:
                    link_idents.add(ident)
                if name == "device":
                    inverse_found = True

    if not inverse_found:
        return False, "No inverse 'device' relationship was added on the interface side"
    if link_idents != {expected}:
        return False, (
            f"Device/Interface identifiers must reuse '{expected}' verbatim; "
            f"found {sorted(link_idents)} — inventing a new identifier and renaming "
            "the forward side is the antipattern (immutable identifier)"
        )
    return True, f"Inverse reuses the forward identifier '{expected}' verbatim"


# ---------------------------------------------------------------------------
# Canonical key order (skills/infrahub-managing-schemas/rules/format-schema-files.md)
# ---------------------------------------------------------------------------
#
# PyYAML builds plain dicts, and dicts preserve insertion order, so the parsed
# document reflects the authored key order of the file. Every check below is
# therefore a pure structural assertion on the parsed schema — no CLI needed.

# Top-level keys, in canonical order. `version` leads; the entity sections
# follow in this order. Keys not listed are ignored.
_FILE_ORDER = ["version", "generics", "nodes", "extensions"]

# The keys an entity (node or generic) must lead with, and the two long list
# keys it must end with.
_ENTITY_LEADING = ["name", "namespace"]
_ENTITY_TRAILING = ["attributes", "relationships"]

# Canonical order of the keys inside a single dropdown choice.
_CHOICE_ORDER = ["name", "label", "description", "color"]

# An entry under `extensions.nodes` targets an existing kind, so `kind` leads
# where a node would lead with name/namespace. The trailing lists are the same.
_EXTENSION_LEADING = ["kind"]


def _relative_order_ok(keys: list[str], canonical: list[str]) -> bool:
    """True if the canonical keys present in ``keys`` appear in canonical order."""
    present = [key for key in keys if key in canonical]
    return present == sorted(present, key=canonical.index)


def _all_extension_nodes(schema: dict) -> list[dict]:
    """Return the node entries declared under the top-level `extensions` block."""
    extensions = schema.get("extensions") or {}
    if not isinstance(extensions, dict):
        return []
    return extensions.get("nodes", []) or []


def check_file_key_order(schema: dict, **_: Any) -> tuple[bool, str]:
    """Top-level keys follow version -> generics -> nodes -> extensions."""
    if not schema:
        return False, "No schema content to inspect"

    keys = list(schema.keys())
    if not _relative_order_ok(keys, _FILE_ORDER):
        present = [key for key in keys if key in _FILE_ORDER]
        return False, (
            f"Top-level keys are ordered {present}; canonical order is "
            "version -> generics -> nodes -> extensions"
        )
    return True, "Top-level keys are in canonical order"


def _entity_key_order_error(entity: dict, leading_order: list[str], label: str) -> str | None:
    """Return an error string if one entity's keys break the canonical order."""
    keys = list(entity.keys())

    if not _relative_order_ok(keys, leading_order):
        return (
            f"{label}: identity keys are ordered "
            f"{[key for key in keys if key in leading_order]}; canonical order is "
            f"{' then '.join(leading_order)}"
        )

    leading = [key for key in keys if key in leading_order]
    if keys[: len(leading)] != leading:
        return f"{label}: identity keys {leading} are not first; file leads with {keys[: len(leading) + 1]}"

    trailing = [key for key in keys if key in _ENTITY_TRAILING]
    if not _relative_order_ok(keys, _ENTITY_TRAILING):
        return f"{label}: 'relationships' precedes 'attributes'; attributes come first"
    if trailing and keys[-len(trailing) :] != trailing:
        return (
            f"{label}: {trailing} must be the last key(s); the entry instead ends with "
            f"{keys[-len(trailing) :]}"
        )
    return None


def check_entity_key_order(schema: dict, **_: Any) -> tuple[bool, str]:
    """Nodes/generics lead with name/namespace (extensions with kind) and end with the lists."""
    entities = _all_generics(schema) + _all_nodes(schema)
    extensions = _all_extension_nodes(schema)
    if not entities and not extensions:
        return False, "No nodes, generics, or extensions found"

    for entity in entities:
        if not isinstance(entity, dict):
            continue
        error = _entity_key_order_error(entity, _ENTITY_LEADING, _full_kind(entity) or "<unnamed>")
        if error:
            return False, error

    for extension in extensions:
        if not isinstance(extension, dict):
            continue
        label = f"extensions.nodes[{extension.get('kind', '<unnamed>')}]"
        error = _entity_key_order_error(extension, _EXTENSION_LEADING, label)
        if error:
            return False, error

    counted = [f"{len(entities)} node(s)/generic(s)"]
    if extensions:
        counted.append(f"{len(extensions)} extension(s)")
    return True, f"Canonical key order on {' and '.join(counted)}"


def _labelled_entities(schema: dict) -> list[tuple[str, dict]]:
    """Every node, generic, and extension entry paired with a label for messages."""
    labelled: list[tuple[str, dict]] = [
        (_full_kind(entity) or "<unnamed>", entity)
        for entity in _all_generics(schema) + _all_nodes(schema)
        if isinstance(entity, dict)
    ]
    labelled += [
        (f"extensions.nodes[{extension.get('kind', '<unnamed>')}]", extension)
        for extension in _all_extension_nodes(schema)
        if isinstance(extension, dict)
    ]
    return labelled


def check_order_weight_key_last(schema: dict, **_: Any) -> tuple[bool, str]:
    """order_weight is the final key of every attribute and relationship that has it."""
    entities = _labelled_entities(schema)
    if not entities:
        return False, "No nodes, generics, or extensions found"

    seen = 0
    for kind, entity in entities:
        for section, items in (("attribute", _all_attrs(entity)), ("relationship", _all_rels(entity))):
            for item in items:
                if not isinstance(item, dict) or "order_weight" not in item:
                    continue
                seen += 1
                keys = list(item.keys())
                if keys[-1] != "order_weight":
                    return False, (
                        f"{kind}.{item.get('name', '<unnamed>')} ({section}): 'order_weight' is "
                        f"followed by {keys[keys.index('order_weight') + 1 :]}; it must be the last key"
                    )

    if seen == 0:
        return False, "No attribute or relationship declares order_weight"
    return True, f"'order_weight' is the last key on all {seen} item(s) that declare it"


def check_choice_key_order(schema: dict, **_: Any) -> tuple[bool, str]:
    """Dropdown choice keys follow name -> label -> description -> color."""
    seen = 0
    for kind, entity in _labelled_entities(schema):
        for attr in _all_attrs(entity):
            if not isinstance(attr, dict):
                continue
            choices = attr.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                seen += 1
                keys = list(choice.keys())
                if keys[0] != "name":
                    return False, (
                        f"{kind}.{attr.get('name', '<unnamed>')}: choice "
                        f"'{choice.get('name', '?')}' does not lead with 'name' (found '{keys[0]}')"
                    )
                if not _relative_order_ok(keys, _CHOICE_ORDER):
                    present = [key for key in keys if key in _CHOICE_ORDER]
                    return False, (
                        f"{kind}.{attr.get('name', '<unnamed>')}: choice "
                        f"'{choice.get('name', '?')}' keys ordered {present}; canonical order is "
                        "name -> label -> description -> color"
                    )

    if seen == 0:
        return False, "No dropdown choices found to inspect"
    return True, f"All {seen} dropdown choice(s) are in canonical key order"




def _entities(schema: dict) -> list[tuple[str, dict]]:
    """Yield ``(section, entity)`` for every node and generic in the schema."""
    out: list[tuple[str, dict]] = []
    for section in ("generics", "nodes"):
        for entity in schema.get(section) or []:
            if isinstance(entity, dict):
                out.append((section, entity))
    return out


# ---------------------------------------------------------------------------
# Reuse and generic membership
#
# The Builtin namespace on a bare instance is exactly four kinds; there is no
# location kind in the platform core. A marketplace kind is a carried
# dependency, so inheriting one without provenance produces a schema that
# loads where it was developed and fails on a clean instance.
#
# The kind sets below are the platform's real ones, read from
# backend/infrahub/core/schema/definitions in Infrahub v1.10.8. Trusting a
# namespace prefix instead would let an invented `CoreLocation` pass the very
# check written to catch it, so membership is exact rather than by prefix.
# ---------------------------------------------------------------------------

_BUILTIN_KINDS = frozenset(
    {"BuiltinIPAddress", "BuiltinIPNamespace", "BuiltinIPPrefix", "BuiltinTag"}
)

_PLATFORM_KINDS = _BUILTIN_KINDS | frozenset(
    {
        # Ipam
        "IpamNamespace",
        # Internal
        "InternalAccountToken", "InternalExternalIdentity", "InternalIPPrefixAvailable",
        "InternalIPRangeAvailable", "InternalRefreshToken",
        # Lineage
        "LineageOwner", "LineageSource",
        # Core
        "CoreAccount", "CoreAccountGroup", "CoreAccountRole", "CoreArtifact",
        "CoreArtifactCheck", "CoreArtifactDefinition", "CoreArtifactTarget",
        "CoreArtifactThread", "CoreArtifactValidator", "CoreBasePermission",
        "CoreChangeComment", "CoreChangeThread", "CoreCheck", "CoreCheckDefinition",
        "CoreComment", "CoreCredential", "CoreCustomWebhook", "CoreDataCheck",
        "CoreDataValidator", "CoreEnvKeyValue", "CoreFileCheck", "CoreFileObject",
        "CoreFileThread", "CoreGeneratorAwareGroup", "CoreGeneratorCheck",
        "CoreGeneratorDefinition", "CoreGeneratorGroup", "CoreGeneratorInstance",
        "CoreGeneratorValidator", "CoreGenericAccount", "CoreGenericRepository",
        "CoreGlobalPermission", "CoreGraphQLQuery", "CoreGraphQLQueryGroup", "CoreGroup",
        "CoreIPAddressPool", "CoreIPPool", "CoreIPPrefixPool", "CoreKeyValue", "CoreMenu",
        "CoreMenuItem", "CoreNode", "CoreNumberPool", "CoreObjectComponentTemplate",
        "CoreObjectPermission", "CoreObjectTemplate", "CoreObjectThread",
        "CorePasswordCredential", "CoreProfile", "CoreProposedChange",
        "CoreReadOnlyRepository", "CoreRepository", "CoreRepositoryGroup",
        "CoreRepositoryValidator", "CoreResourcePool", "CoreSchemaCheck",
        "CoreSchemaValidator", "CoreStandardCheck", "CoreStandardGroup",
        "CoreStandardWebhook", "CoreStaticKeyValue", "CoreTaskTarget", "CoreThread",
        "CoreThreadComment", "CoreTransformJinja2", "CoreTransformPython",
        "CoreTransformation", "CoreUserValidator", "CoreValidator", "CoreWebhook",
        "CoreWeightedPoolResource",
    }
)

# Namespaces the platform reserves. A kind in one of these that is not in
# _PLATFORM_KINDS is invented, not core.
_PLATFORM_NAMESPACES = ("Builtin", "Core", "Internal", "Ipam", "Lineage")

# Profile<Kind> and Template<Kind> are generated by the platform from a
# concrete kind, so they are real exactly when that kind is.
_DERIVED_PREFIXES = ("Profile", "Template")

# A version pin, a commit pin, or -- for the documented default
# invocation, which fetches "latest published" -- the word "latest" next to
# a date, which is what a reader actually needs in order to tell later
# whether the local copy has drifted.
_PROVENANCE_VERSION_RE = re.compile(
    r"(?:-v|--version)\s+v?\d+\.\d+"
    r"|version[\s:=]+v?\d+\.\d+"
    r"|\b(?:commit|sha|rev)[\s:=]+[0-9a-f]{7,40}\b"
    r"|\blatest\b[^\n]{0,40}\d{4}-\d{2}-\d{2}"
    r"|\d{4}-\d{2}-\d{2}[^\n]{0,40}\blatest\b",
    re.IGNORECASE,
)


def _defined_kinds(schema: dict) -> set[str]:
    return {
        f"{e.get('namespace', '')}{e.get('name', '')}" for _section, e in _entities(schema)
    }


def _referenced_external_kinds(schema: dict) -> set[str]:
    """Kinds referenced but not defined in this schema file."""
    defined = _defined_kinds(schema)
    referenced: set[str] = set()
    for _section, entity in _entities(schema):
        referenced.update(entity.get("inherit_from") or [])
        for field in ("parent", "children", "menu_placement"):
            value = entity.get(field)
            if isinstance(value, str) and value:
                referenced.add(value)
        for rel in entity.get("relationships") or []:
            if isinstance(rel, dict) and rel.get("peer"):
                referenced.add(rel["peer"])
    return {k for k in referenced if k and k not in defined}


def _comment_runs(raw_text: str) -> list[str]:
    """Maximal runs of consecutive comment lines, each joined into one string.

    A `#`-only line ends a run. Without that, a file header separated into
    paragraphs by bare `#` lines is one block, and per-block provenance
    scoping is per-file scoping again: one `marketplace get` line vouches
    for every kind named anywhere in the header.
    """
    runs: list[str] = []
    current: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and stripped.lstrip("#").strip():
            current.append(line)
        elif current:
            runs.append("\n".join(current))
            current = []
    if current:
        runs.append("\n".join(current))
    return runs


def _provenance_blocks(raw_text: str) -> list[str]:
    """Comment runs that carry an `infrahubctl marketplace get` line.

    Provenance is read per block rather than per file so a single command
    comment cannot vouch for unrelated kinds elsewhere in the file, and so the
    schema's own `version:` key cannot pass as a marketplace version.
    """
    return [run for run in _comment_runs(raw_text) if "marketplace get" in run]


def check_external_kinds_are_core_or_sourced(
    schema: dict, *, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """Every kind referenced but not defined must be core, or carry provenance.

    A `Builtin*` or `Core*` spelling that is not a kind the platform ships is
    the specific trap: it reads as a platform guarantee and is not one.
    Marketplace-sourced kinds are fine, but the provenance comment has to name
    the kind it vouches for, so a clean deploy loads it first.
    """
    external = _referenced_external_kinds(schema)
    if not external:
        return True, "no external kinds referenced"

    defined = _defined_kinds(schema)
    blocks = _provenance_blocks(raw_text)

    problems: list[str] = []
    for kind in sorted(external):
        if kind in _PLATFORM_KINDS:
            continue
        if kind.startswith(_PLATFORM_NAMESPACES):
            problems.append(
                f"{kind} is spelled like a platform kind, but Infrahub ships no "
                f"such kind (the Builtin namespace is exactly {sorted(_BUILTIN_KINDS)})"
            )
            continue
        derived_base = next(
            (kind[len(p):] for p in _DERIVED_PREFIXES if kind.startswith(p) and kind != p),
            None,
        )
        if derived_base and (derived_base in defined or derived_base in _PLATFORM_KINDS):
            continue
        if not any(re.search(rf"\b{re.escape(kind)}\b", block) for block in blocks):
            problems.append(
                f"{kind} is not a platform kind and no `infrahubctl marketplace get` "
                "provenance comment names it"
            )
    if problems:
        return False, "; ".join(problems)
    return True, f"external kinds accounted for: {sorted(external)}"


def check_records_marketplace_provenance(
    schema: dict, *, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """A reused or vendored shape must record identifier and version.

    Without both, nobody can tell later whether the local copy has drifted
    from upstream or was changed on purpose. The version has to sit in the
    provenance comment itself, so the file's own `version:` key does not
    stand in for a marketplace version.
    """
    blocks = _provenance_blocks(raw_text)
    if not blocks:
        return False, "no `infrahubctl marketplace get` provenance comment recorded"
    if not any(re.search(r"marketplace get\s+\S+/\S+", block) for block in blocks):
        return False, "provenance records no `<namespace>/<name>` marketplace identifier"
    if not any(_PROVENANCE_VERSION_RE.search(block) for block in blocks):
        return False, (
            "provenance names no version; record `-v <version>`, a commit pin, "
            "or -- if you took the default `marketplace get <ns>/<name>`, which "
            "fetches the latest published version -- `latest at <YYYY-MM-DD>` "
            "in the same comment"
        )
    return True, "provenance records the marketplace identifier and a version"


def check_corrects_builtin_core_premise(
    schema: dict, *, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """The file must say what the platform actually ships, not repeat the myth.

    The premise under test is "it is built into Infrahub". Correcting it means
    naming the four kinds the Builtin namespace really has and saying the
    candidate is not one of them.
    """
    comments = "\n".join(_comment_runs(raw_text))
    if not comments:
        return False, "file records no comments, so it corrects nothing"

    # What Builtin holds, stated either by naming the kinds or by describing
    # the set. Requiring all four literal names graded transcription: "the
    # Builtin namespace ships only the tag kind and the three IPAM
    # primitives" is correct and complete and was failing, while a list of
    # the four names plus a false claim was passing.
    named = [k for k in _BUILTIN_KINDS if k in comments]
    described = re.search(
        r"\bbuiltin\b[^\n]{0,120}\b(?:tag|ipam|ip address|ip prefix|ip namespace)\b",
        comments,
        re.IGNORECASE,
    )
    if len(named) < len(_BUILTIN_KINDS) and not described:
        return False, (
            "comments do not say what the Builtin namespace holds; name the "
            f"kinds ({sorted(_BUILTIN_KINDS)}) or describe the set"
        )

    # And the claim under test: the *reused* kind is not one of them. A
    # denial whose subject is a Builtin kind is the opposite claim --
    # "BuiltinTag is not core" is false, and asserting it should not earn
    # the check the way a token list did.
    denial_re = re.compile(
        r"\bnot\b[^\n]{0,80}\b(?:core|built[\s-]?in|platform|shipped)\b"
        r"|\b(?:no|not a)\b[^\n]{0,80}\blocation\b[^\n]{0,40}\b(?:kind|core|generic)\b"
        r"|\bships no\b[^\n]{0,60}\blocation\b",
        re.IGNORECASE,
    )
    denial = None
    for sentence in re.split(r"(?<=[.;])\s+|\n", comments):
        hit = denial_re.search(sentence)
        if not hit:
            continue
        if any(kind in sentence for kind in _BUILTIN_KINDS):
            continue  # a Builtin kind *is* core; this denies the wrong thing
        denial = hit
        break
    if denial is None:
        return False, (
            "comments say what Builtin holds but never say the reused kind is "
            "not platform core (a denial naming a Builtin kind does not count: "
            "those are core)"
        )
    return True, "comments state what Builtin ships and that the reused kind is not core"


def check_names_kind_verification_command(
    schema: dict, *, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """The file must name a command that can actually confirm the kind.

    `infrahubctl schema show <Kind>` resolves nodes and generics alike.
    `infrahubctl schema list` prints node kinds only, so it cannot confirm a
    generic, which is what reuse candidates usually are.
    """
    comments = "\n".join(_comment_runs(raw_text))
    if re.search(r"infrahubctl\s+schema\s+show\b", comments):
        return True, "comments name `infrahubctl schema show <Kind>`"
    if re.search(r"infrahubctl\s+schema\s+list\b", comments):
        return False, (
            "comments name only `infrahubctl schema list`, which prints node "
            "kinds and cannot confirm a generic; use `schema show <Kind>`"
        )
    return False, "comments name no command that confirms a kind exists"


def check_records_subset_rationale(
    schema: dict, *, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """A partial adoption must record what was taken and why the rest was not.

    The exclusion reason is the part that stops the next reader repeating the
    evaluation, and it is the part that shows the file was judged per generic
    rather than as a unit.
    """
    blocks = _provenance_blocks(raw_text)
    if not blocks:
        return False, "no `infrahubctl marketplace get` provenance comment recorded"

    text = "\n".join(blocks)
    taken = re.search(r"\b(taken|adopted|reused|kept|using only|only the)\b", text, re.I)
    excluded = re.search(
        r"\b(excluded|omitted|left out|not taken|dropped|skipped|rejected)\b", text, re.I
    )
    if not taken:
        return False, "provenance does not say which generic or node was taken"
    if not excluded:
        return False, "provenance does not say what was excluded, or why"
    return True, "provenance records what was taken and what was excluded"


def _python_code_only(src: str) -> str:
    """``src`` with comments and docstrings removed.

    Keyword matching over raw source counts a `# TODO: read inherit_from
    properly; report added / removed kinds` comment as an implementation of
    exactly what it says is missing. Other string literals are kept, because
    `n.get("inherit_from")` is how the test does the reading.
    """
    try:
        tokens = [
            t for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type != tokenize.COMMENT
        ]
        without_comments = tokenize.untokenize(tokens)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        without_comments = re.sub(r"#[^\n]*", "", src)
    try:
        tree = ast.parse(without_comments)
    except SyntaxError:
        return without_comments
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            first.value.value = ""
    return ast.unparse(tree)


def _pinned_kind_sets(src: str) -> list[tuple[str, set[str]]]:
    """Assigned literal collections of kind-looking strings, by target name."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: list[tuple[str, set[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if isinstance(value, ast.Call) and value.args:
            value = value.args[0]  # set([...]) / frozenset([...])
        if not isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            continue
        items = {
            e.value for e in value.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
        if not items or not all(re.fullmatch(r"[A-Z][A-Za-z0-9]+", i) for i in items):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        for target in targets:
            if isinstance(target, ast.Name):
                out.append((target.id, items))
    return out


def check_generic_implementer_set_pinned(
    schema: dict, *, sources: dict[str, str] | None = None, **_: Any
) -> tuple[bool, str]:
    """The offline test must pin the implementer set, not query a live instance.

    An assertion against a loaded graph proves what the platform returns; an
    assertion over the schema YAML proves what the schema declares, and only
    that one runs fast enough to block a pull request.

    The pinned set is compared against the implementers the schema actually
    declares. Without that link the check was keyword matching: a stub whose
    only mention of `inherit_from`, `added` and `removed` was inside a
    `# TODO` comment scored full marks.
    """
    test_src = (sources or {}).get("py", "")
    if not test_src.strip():
        return False, "no Python test produced"
    code = _python_code_only(test_src)
    if re.search(r"InfrahubClient|infrahub_sdk|\.execute_graphql\(|await client", code):
        return False, (
            "the test reaches a live instance; pin the set over the schema YAML "
            "so the gate runs offline"
        )
    if not re.search(r"inherit_from", code):
        return False, "the test never reads `inherit_from`, so it pins nothing"
    if not re.search(r"\bassert\b", code):
        return False, "the test asserts nothing"
    if not (re.search(r"\badded\b", code, re.I) and re.search(r"\bremoved\b", code, re.I)):
        return False, (
            "the failure path does not report what was added and removed, so the "
            "fix is not mechanical"
        )

    declared = _implementers_by_generic(schema)
    if not declared:
        return False, "the schema declares no generic with implementers to pin"
    pinned = _pinned_kind_sets(test_src)
    if not pinned:
        return False, "the test declares no pinned expected implementer set"
    for _name, items in pinned:
        for generic, kinds in declared.items():
            if items == kinds:
                return True, (
                    f"the test pins {sorted(kinds)} for {generic}, matching the "
                    "schema, offline, and reports added/removed"
                )
    return False, (
        f"the pinned set(s) {[sorted(i) for _n, i in pinned]} match no generic's "
        f"implementers in the schema {({g: sorted(k) for g, k in declared.items()})}; "
        "the pin has to be of what the schema declares"
    )


def _implementers_by_generic(schema: dict) -> dict[str, set[str]]:
    """Generics declared in this file, mapped to the kinds that inherit them."""
    generics = {
        f"{g.get('namespace', '')}{g.get('name', '')}"
        for _s, g in _entities(schema)
        if _s == "generics"
    }
    out: dict[str, set[str]] = {}
    for section, entity in _entities(schema):
        if section != "nodes":
            continue
        kind = f"{entity.get('namespace', '')}{entity.get('name', '')}"
        for parent in entity.get("inherit_from") or []:
            if parent in generics:
                out.setdefault(parent, set()).add(kind)
    return out


def check_generic_membership_consumers_noted(
    schema: dict, *, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """Joining a generic must be recorded as a decision about its consumers.

    Adding an implementer changes what every query, constraint, and consumer
    over that generic answers, and nothing in the platform flags it.
    """
    comments = "\n".join(_comment_runs(raw_text))
    if not comments:
        return False, "file records no comments about the membership change"
    # The prompt hands the model "`infrahubctl schema check` passes either
    # way", so the words in it cannot be what earns the check.
    prompt_echo = re.compile(
        r"infrahubctl\s+schema\s+check|schema\s+check\s+passes", re.IGNORECASE
    )
    scored = prompt_echo.sub(" ", comments)
    hits = sorted(
        {
            term
            for term, pattern in (
                ("queries", r"\bquer(?:y|ies)\b"),
                ("constraints", r"uniqueness_constraints|human_friendly_id|constraint"),
                (
                    "consumers",
                    r"\bconsumer|\bgenerator|\btransform|check[_\s-]?definition"
                    r"|\biterat|\bsums?\b|\bsummed\b|\bsumming\b|\breport\b",
                ),
            )
            if re.search(pattern, scored, re.IGNORECASE)
        }
    )
    # And the comments have to be about the generic that gained the
    # implementer, not consumer nouns floating anywhere in the file.
    declared = _implementers_by_generic(schema)
    if declared and not any(generic in scored for generic in declared):
        return False, (
            "comments never name the generic that gained an implementer "
            f"({sorted(declared)}), so they record no decision about it"
        )
    if len(hits) < 2:
        return False, (
            "comments name fewer than two consumer classes affected by the new "
            f"implementer (found {hits or 'none'}); name queries, constraints and "
            "code that iterates the generic"
        )
    return True, f"comments name affected consumers: {hits}"


CHECKS: dict[str, Any] = {
    "attr-min-length": check_attr_min_length,
    "external-kinds-core-or-sourced": check_external_kinds_are_core_or_sourced,
    "records-marketplace-provenance": check_records_marketplace_provenance,
    "corrects-builtin-core-premise": check_corrects_builtin_core_premise,
    "names-kind-verification-command": check_names_kind_verification_command,
    "records-subset-rationale": check_records_subset_rationale,
    "generic-implementer-set-pinned": check_generic_implementer_set_pinned,
    "generic-membership-consumers-noted": check_generic_membership_consumers_noted,
    "dropdown-for-status": check_dropdown_for_status,
    "no-deprecated-string": check_no_deprecated_string,
    "full-kind-references": check_full_kind_references,
    "human-friendly-id": check_human_friendly_id,
    "display-label-singular": check_display_label_singular,
    "schema-version": check_schema_version,
    "matching-identifiers": check_matching_identifiers,
    "inverse-reuses-forward-identifier": check_inverse_reuses_forward_identifier,
    "hierarchical-generic": check_hierarchical_generic,
    "inherit-from-generic": check_inherit_from_generic,
    "root-no-parent": check_root_no_parent,
    "correct-hierarchy-chain": check_correct_hierarchy_chain,
    "two-endpoint-relationships": check_two_endpoint_relationships,
    "attribute-kind-relationships": check_attribute_kind_relationships,
    "endpoint-device-relationship": check_endpoint_device_relationship,
    "parent-rel-optional-false": check_parent_rel_optional_false,
    "parent-rel-single": check_parent_rel_single,
    "computed-jinja2-readonly": check_computed_jinja2_readonly,
    "computed-jinja2-kind": check_computed_jinja2_kind,
    "on-delete-cascade-present": check_on_delete_cascade_present,
    "generate-template-concrete-only": check_generate_template_concrete_only,
    "generate-profile-concrete-only": check_generate_profile_concrete_only,
    "core-artifact-target-concrete": check_core_artifact_target_concrete,
    "core-file-object-inherited": check_core_file_object_inherited,
    "file-object-on-node-not-generic": check_file_object_on_node_not_generic,
    "no-reserved-file-attrs": check_no_reserved_file_attrs,
    "no-filename-text-bypass": check_no_filename_text_bypass,
    "string-limits": check_string_limits,
    "recommends-branch": check_recommends_branch,
    "explains-default-branch-risk-or-review": check_explains_default_branch_risk_or_review,
    "file-key-order": check_file_key_order,
    "entity-key-order": check_entity_key_order,
    "order-weight-key-last": check_order_weight_key_last,
    "choice-key-order": check_choice_key_order,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_path: Path,
    raw_text: str | None = None,
    sources: dict[str, str] | None = None,
) -> dict:
    """Run named checks against a schema file and return skillgrade JSON.

    Parameters
    ----------
    check_names:
        List of assertion names from the ``CHECKS`` registry.
    output_path:
        Path to the schema YAML file produced by the model.
    raw_text:
        Optional pre-loaded raw text (used by checks that inspect comments).
        If ``None``, the file is read from ``output_path``.
    sources:
        Optional companion files keyed by extension (for example ``{"py": ...}``)
        for tasks that produce more than the schema YAML.

    Returns
    -------
    dict with keys:
        - ``score`` (float 0.0-1.0)
        - ``details`` (str summary)
        - ``checks`` (list of ``{"name", "passed", "message"}``)

    Raises
    ------
    KeyError
        If any name in ``check_names`` is not in ``CHECKS``.
    """
    schema, file_raw = load_output(output_path)
    if raw_text is None:
        raw_text = file_raw

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            ok, msg = fn(schema, raw_text=raw_text, sources=sources or {})
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"

        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0

    passed_names = [e["name"] for e in entries if e["passed"]]
    failed_names = [e["name"] for e in entries if not e["passed"]]
    if failed_names:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed_names)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}
