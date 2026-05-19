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


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "attr-min-length": check_attr_min_length,
    "dropdown-for-status": check_dropdown_for_status,
    "no-deprecated-string": check_no_deprecated_string,
    "full-kind-references": check_full_kind_references,
    "human-friendly-id": check_human_friendly_id,
    "display-label-singular": check_display_label_singular,
    "schema-version": check_schema_version,
    "matching-identifiers": check_matching_identifiers,
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
    "core-artifact-target-concrete": check_core_artifact_target_concrete,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_path: Path,
    raw_text: str | None = None,
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
            ok, msg = fn(schema, raw_text=raw_text)
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
