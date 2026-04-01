#!/usr/bin/env python3
"""
Skill evaluation runner for CI/CD and local use.

Runs evaluation prompts with and without skill context using the Claude CLI,
grades schema outputs programmatically against assertions, and generates
benchmark reports (JSON + Markdown).

Usage:
    python scripts/run_evals.py
    python scripts/run_evals.py --eval-file evaluations/schema-creator.json
    python scripts/run_evals.py --output-dir eval-results --model claude-sonnet-4-6
"""

import argparse
import json
import os
import subprocess
import sys
import time
import textwrap
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_PATHS = {
    "infrahub-schema-creator": "skills/schema-creator/SKILL.md",
    "infrahub-object-creator": "skills/infrahub-object-creator/SKILL.md",
}


# ---------------------------------------------------------------------------
# Claude CLI runner
# ---------------------------------------------------------------------------

def run_claude_prompt(prompt: str, output_path: Path, with_skill: bool,
                      skill_path: str | None = None,
                      model: str | None = None) -> dict:
    """Run a single prompt via ``claude -p`` and return timing metadata."""
    output_path.mkdir(parents=True, exist_ok=True)
    schema_file = output_path / "schema.yml"

    if with_skill and skill_path:
        full_prompt = textwrap.dedent(f"""\
            Read the skill at {skill_path} and follow its workflow and rules to accomplish this task.

            Task: {prompt}

            Save ONLY the final schema YAML file to: {schema_file}
        """)
    else:
        full_prompt = textwrap.dedent(f"""\
            Do NOT read any files from the skills/ directory.
            Use only your general knowledge of Infrahub.

            Task: {prompt}

            Save ONLY the final schema YAML file to: {schema_file}
        """)

    cmd = [
        "claude",
        "-p", full_prompt,
        "--output-format", "json",
        "--max-turns", "25",
    ]
    if model:
        cmd.extend(["--model", model])

    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "cli"}
    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=300, cwd=str(REPO_ROOT), env=env,
        )
    except subprocess.TimeoutExpired:
        timing = {"total_tokens": 0, "duration_ms": 300_000,
                  "total_duration_seconds": 300.0, "error": "timeout"}
        with open(output_path / "timing.json", "w") as f:
            json.dump(timing, f, indent=2)
        return timing
    duration = time.time() - start

    total_tokens = 0
    cost_usd = 0.0
    try:
        out = json.loads(result.stdout)
        total_tokens = out.get("num_tokens", 0) or 0
        cost_usd = out.get("session_cost", 0.0) or 0.0
    except (json.JSONDecodeError, TypeError):
        pass

    timing = {
        "total_tokens": total_tokens,
        "duration_ms": int(duration * 1000),
        "total_duration_seconds": round(duration, 1),
        "cost_usd": cost_usd,
        "returncode": result.returncode,
    }
    with open(output_path / "timing.json", "w") as f:
        json.dump(timing, f, indent=2)
    return timing


# ---------------------------------------------------------------------------
# Programmatic schema graders
# ---------------------------------------------------------------------------

def _all_nodes(schema: dict) -> list[dict]:
    return schema.get("nodes", [])


def _all_generics(schema: dict) -> list[dict]:
    return schema.get("generics", [])


def _all_attrs(node: dict) -> list[dict]:
    return node.get("attributes", [])


def _all_rels(node: dict) -> list[dict]:
    return node.get("relationships", [])


def _full_kind(node: dict) -> str:
    ns = node.get("namespace", "")
    name = node.get("name", "")
    return f"{ns}{name}"


def check_attr_min_length(schema: dict, **_) -> tuple[bool, str]:
    """All attribute names must be >= 3 characters."""
    short = []
    for node in _all_nodes(schema) + _all_generics(schema):
        for attr in _all_attrs(node):
            if len(attr.get("name", "")) < 3:
                short.append(f"{_full_kind(node)}.{attr['name']}")
    if short:
        return False, f"Short attribute names found: {', '.join(short)}"
    return True, "All attribute names >= 3 characters"


def check_dropdown_for_status(schema: dict, **_) -> tuple[bool, str]:
    """Status attribute uses kind: Dropdown with choices."""
    for node in _all_nodes(schema):
        for attr in _all_attrs(node):
            if attr.get("name") == "status":
                if attr.get("kind") != "Dropdown":
                    return False, f"{_full_kind(node)}.status uses kind: {attr.get('kind')}, expected Dropdown"
                if not attr.get("choices"):
                    return False, f"{_full_kind(node)}.status has no choices defined"
                return True, f"{_full_kind(node)}.status uses Dropdown with {len(attr['choices'])} choices"
    return False, "No status attribute found"


def check_no_deprecated_string(schema: dict, **_) -> tuple[bool, str]:
    """No attribute should use the deprecated 'String' kind."""
    found = []
    for node in _all_nodes(schema) + _all_generics(schema):
        for attr in _all_attrs(node):
            if attr.get("kind") == "String":
                found.append(f"{_full_kind(node)}.{attr['name']}")
    if found:
        return False, f"Deprecated 'String' kind used: {', '.join(found)}"
    return True, "All attributes use 'Text' (not deprecated 'String')"


def check_full_kind_references(schema: dict, **_) -> tuple[bool, str]:
    """All peer references use full Namespace+Name kind."""
    defined_kinds = set()
    for node in _all_nodes(schema) + _all_generics(schema):
        defined_kinds.add(_full_kind(node))

    short = []
    for node in _all_nodes(schema) + _all_generics(schema):
        for rel in _all_rels(node):
            peer = rel.get("peer", "")
            if not peer:
                continue
            # Skip well-known external kinds
            if peer.startswith("Builtin") or peer.startswith("Infra"):
                continue
            # A peer is "short" if it matches a node name but not the full kind
            names_only = {n.get("name", "") for n in _all_nodes(schema) + _all_generics(schema)}
            if peer in names_only and peer not in defined_kinds:
                short.append(f"{_full_kind(node)}.{rel['name']} -> {peer}")
    if short:
        return False, f"Short peer references: {', '.join(short)}"
    return True, "All peer references use full Namespace+Name kind"


def check_human_friendly_id(schema: dict, **_) -> tuple[bool, str]:
    """human_friendly_id is defined on all nodes."""
    missing = []
    for node in _all_nodes(schema):
        if not node.get("human_friendly_id"):
            # Check if inherited from a generic
            inherits = node.get("inherit_from", [])
            if inherits:
                for generic in _all_generics(schema):
                    if _full_kind(generic) in inherits and generic.get("human_friendly_id"):
                        break
                else:
                    missing.append(_full_kind(node))
            else:
                missing.append(_full_kind(node))
    if missing:
        return False, f"Missing human_friendly_id: {', '.join(missing)}"
    return True, "human_friendly_id defined on all nodes"


def check_display_label_singular(schema: dict, **_) -> tuple[bool, str]:
    """Uses display_label (singular), not deprecated display_labels (plural)."""
    bad = []
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


def check_schema_version(schema: dict, **_) -> tuple[bool, str]:
    """Schema starts with version: '1.0'."""
    version = schema.get("version")
    if version == "1.0":
        return True, "version: '1.0'"
    return False, f"version is '{version}', expected '1.0'"


def check_matching_identifiers(schema: dict, **_) -> tuple[bool, str]:
    """All relationship identifier pairs match between both sides."""
    # Build a map of identifier -> list of (node_kind, rel_name)
    id_map: dict[str, list[tuple[str, str]]] = {}
    for node in _all_nodes(schema) + _all_generics(schema):
        for rel in _all_rels(node):
            ident = rel.get("identifier")
            if ident:
                kind = _full_kind(node)
                id_map.setdefault(ident, []).append((kind, rel.get("name", "")))

    # Each identifier should appear at least twice (both sides)
    orphans = []
    for ident, usages in id_map.items():
        if len(usages) < 2:
            # Skip if peer is external (not defined in this schema)
            rel_node_kind = usages[0][0]
            for node in _all_nodes(schema) + _all_generics(schema):
                if _full_kind(node) == rel_node_kind:
                    for rel in _all_rels(node):
                        if rel.get("identifier") == ident:
                            peer = rel.get("peer", "")
                            defined = {_full_kind(n) for n in _all_nodes(schema) + _all_generics(schema)}
                            if peer not in defined:
                                break  # External peer, skip
                    else:
                        orphans.append(f"{ident} (only on {usages[0][0]}.{usages[0][1]})")
                    break

    if orphans:
        return False, f"Orphan identifiers (only one side defined): {', '.join(orphans)}"
    return True, "All relationship identifiers match between both sides"


def check_hierarchical_generic(schema: dict, **_) -> tuple[bool, str]:
    """A generic is defined with hierarchical: true."""
    for generic in _all_generics(schema):
        if generic.get("hierarchical") is True:
            return True, f"{_full_kind(generic)} has hierarchical: true"
    return False, "No generic with hierarchical: true found"


def check_inherit_from_generic(schema: dict, **_) -> tuple[bool, str]:
    """All nodes inherit_from the hierarchical generic using its full kind."""
    hier_kind = None
    for generic in _all_generics(schema):
        if generic.get("hierarchical") is True:
            hier_kind = _full_kind(generic)
            break
    if not hier_kind:
        return False, "No hierarchical generic found"

    missing = []
    for node in _all_nodes(schema):
        inherits = node.get("inherit_from", [])
        if hier_kind not in inherits:
            missing.append(_full_kind(node))
    if missing:
        return False, f"Nodes not inheriting from {hier_kind}: {', '.join(missing)}"
    return True, f"All nodes inherit from {hier_kind}"


def check_root_no_parent(schema: dict, **_) -> tuple[bool, str]:
    """Root node has parent set to empty string or null."""
    for node in _all_nodes(schema):
        parent = node.get("parent")
        if parent is None or parent == "" or parent == "null":
            return True, f"{_full_kind(node)} has parent: {repr(parent)}"
    return False, "No root node with parent null or empty string found"


def check_correct_hierarchy_chain(schema: dict, **_) -> tuple[bool, str]:
    """Parent/children chain: Region->Site->Room->Rack."""
    nodes_by_name = {}
    for node in _all_nodes(schema):
        name_lower = node.get("name", "").lower()
        nodes_by_name[name_lower] = node

    expected = [("region", "site"), ("site", "room"), ("room", "rack")]
    issues = []
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
            # Normalize to a comparable token: could be a string or a list
            if isinstance(children_val, list):
                children_tokens = [str(v) for v in children_val]
            else:
                children_tokens = [str(children_val)]
            if child_kind not in children_tokens:
                issues.append(f"{_full_kind(parent_node)}.children does not reference {child_kind}")

        parent_val = child_node.get("parent", "")
        parent_kind = _full_kind(parent_node)
        if parent_val:
            if isinstance(parent_val, list):
                parent_tokens = [str(v) for v in parent_val]
            else:
                parent_tokens = [str(parent_val)]
            if parent_kind not in parent_tokens:
                issues.append(f"{_full_kind(child_node)}.parent does not reference {parent_kind}")

    if issues:
        return False, "; ".join(issues)
    return True, "Region->Site->Room->Rack hierarchy is correct"


def check_two_endpoint_relationships(schema: dict, **_) -> tuple[bool, str]:
    """Circuit has two endpoint relationships (side_a/side_z)."""
    for node in _all_nodes(schema):
        if node.get("name", "").lower() == "circuit":
            endpoint_rels = []
            for rel in _all_rels(node):
                name = rel.get("name", "").lower()
                if "endpoint" in name or "side" in name:
                    endpoint_rels.append(rel.get("name"))
            if len(endpoint_rels) >= 2:
                return True, f"Circuit has {len(endpoint_rels)} endpoint relationships: {', '.join(endpoint_rels)}"
            elif len(endpoint_rels) == 1:
                return False, f"Circuit has only 1 endpoint relationship: {endpoint_rels[0]} (expected 2 for side_a/side_z)"
            else:
                return False, "Circuit has no endpoint relationships"
    return False, "No Circuit node found"


def check_attribute_kind_relationships(schema: dict, **_) -> tuple[bool, str]:
    """Circuit-to-Provider uses kind: Attribute with matching identifiers."""
    for node in _all_nodes(schema):
        if node.get("name", "").lower() == "circuit":
            for rel in _all_rels(node):
                peer = rel.get("peer", "").lower()
                if "provider" in peer:
                    kind = rel.get("kind")
                    if kind == "Attribute":
                        return True, f"Circuit.{rel['name']} -> {rel['peer']} uses kind: Attribute"
                    return False, f"Circuit.{rel['name']} -> {rel['peer']} uses kind: {kind}, expected Attribute"
    return False, "No Circuit-to-Provider relationship found"


def check_endpoint_device_relationship(schema: dict, **_) -> tuple[bool, str]:
    """CircuitEndpoint-to-Device uses kind: Attribute with matching identifiers."""
    for node in _all_nodes(schema):
        name = node.get("name", "").lower()
        if "endpoint" in name:
            for rel in _all_rels(node):
                if "device" in rel.get("name", "").lower() or "device" in rel.get("peer", "").lower():
                    kind = rel.get("kind")
                    if kind == "Attribute":
                        return True, f"{_full_kind(node)}.{rel['name']} uses kind: Attribute"
                    return False, f"{_full_kind(node)}.{rel['name']} uses kind: {kind}, expected Attribute"
    return False, "No Endpoint-to-Device relationship found"


# ---------------------------------------------------------------------------
# Menu-creator assertion checks
# ---------------------------------------------------------------------------

def _menu_items(doc: dict) -> list[dict]:
    """Return top-level menu items from spec.data."""
    return doc.get("spec", {}).get("data", []) or []


def _all_menu_leaves(doc: dict) -> list[dict]:
    """Recursively collect all leaf menu items (items with a 'kind' key)."""
    leaves = []
    def _walk(items):
        for item in (items or []):
            if item.get("kind"):
                leaves.append(item)
            children = item.get("children", {})
            if isinstance(children, dict):
                _walk(children.get("data", []))
            elif isinstance(children, list):
                _walk(children)
    _walk(_menu_items(doc))
    return leaves


def _all_menu_items_recursive(doc: dict) -> list[dict]:
    """Recursively collect all menu items at every level."""
    items = []
    def _walk(item_list):
        for item in (item_list or []):
            items.append(item)
            children = item.get("children", {})
            if isinstance(children, dict):
                _walk(children.get("data", []))
            elif isinstance(children, list):
                _walk(children)
    _walk(_menu_items(doc))
    return items


def check_apiversion_and_kind(doc: dict, **_) -> tuple[bool, str]:
    api = doc.get("apiVersion")
    kind = doc.get("kind")
    if api == "infrahub.app/v1" and kind == "Menu":
        return True, "apiVersion: infrahub.app/v1 and kind: Menu"
    return False, f"apiVersion: {api}, kind: {kind}"


def check_spec_data_structure(doc: dict, **_) -> tuple[bool, str]:
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        return False, "No spec key or spec is not a dict"
    data = spec.get("data")
    if not isinstance(data, list):
        return False, f"spec.data is {type(data).__name__}, expected list"
    if len(data) == 0:
        return False, "spec.data is empty"
    return True, f"spec.data is a list with {len(data)} items"


def check_name_and_namespace(doc: dict, **_) -> tuple[bool, str]:
    missing = []
    for item in _all_menu_items_recursive(doc):
        label = item.get("label", item.get("name", "?"))
        if not item.get("name"):
            missing.append(f"{label} missing name")
        if not item.get("namespace"):
            missing.append(f"{label} missing namespace")
    if missing:
        return False, f"Issues: {', '.join(missing)}"
    return True, "All items have name and namespace"


def check_kind_for_schema_links(doc: dict, **_) -> tuple[bool, str]:
    leaves = _all_menu_leaves(doc)
    if not leaves:
        return False, "No leaf items with kind found"
    for item in leaves:
        if item.get("path") and not item.get("kind"):
            return False, f"Item {item.get('name')} uses path instead of kind"
    return True, f"{len(leaves)} items use kind for schema links"


def check_mdi_icons(doc: dict, **_) -> tuple[bool, str]:
    bad = []
    for item in _all_menu_items_recursive(doc):
        icon = item.get("icon", "")
        if not icon:
            bad.append(f"{item.get('name', '?')} has no icon")
        elif not icon.startswith("mdi:"):
            bad.append(f"{item.get('name', '?')} icon '{icon}' missing mdi: prefix")
    if bad:
        return False, f"Icon issues: {', '.join(bad)}"
    return True, "All icons use mdi: prefix"


def check_labels_present(doc: dict, **_) -> tuple[bool, str]:
    missing = []
    for item in _all_menu_items_recursive(doc):
        if not item.get("label"):
            missing.append(item.get("name", "?"))
    if missing:
        return False, f"Missing label on: {', '.join(missing)}"
    return True, "All items have labels"


def check_group_headers_no_kind(doc: dict, **_) -> tuple[bool, str]:
    groups = [i for i in _menu_items(doc)
              if i.get("children") and not i.get("kind") and not i.get("path")]
    if not groups:
        return False, "No top-level group headers without kind/path found"
    bad = [g.get("name", "?") for g in _menu_items(doc)
           if g.get("children") and (g.get("kind") or g.get("path"))]
    if bad:
        return False, f"Group headers with kind/path: {', '.join(bad)}"
    return True, f"{len(groups)} group headers without kind/path"


def check_children_data_wrapper(doc: dict, **_) -> tuple[bool, str]:
    for item in _all_menu_items_recursive(doc):
        children = item.get("children")
        if children is None:
            continue
        if isinstance(children, list):
            return False, f"Item {item.get('name', '?')} has children as a list, expected children.data wrapper"
        if isinstance(children, dict) and "data" in children:
            continue
        return False, f"Item {item.get('name', '?')} has children but no data key"
    return True, "All children use children.data wrapper"


def check_leaf_items_have_kind(doc: dict, **_) -> tuple[bool, str]:
    leaves = _all_menu_leaves(doc)
    if not leaves:
        # Check if there are any items without children that also lack kind
        for item in _all_menu_items_recursive(doc):
            if not item.get("children") and not item.get("kind"):
                return False, f"Leaf item {item.get('name', '?')} has no kind"
        return False, "No leaf items found"
    return True, f"{len(leaves)} leaf items have kind"


def check_correct_grouping(doc: dict, **_) -> tuple[bool, str]:
    groups = {}
    for item in _menu_items(doc):
        label = (item.get("label") or item.get("name") or "").lower()
        children = item.get("children", {})
        child_list = children.get("data", []) if isinstance(children, dict) else children if isinstance(children, list) else []
        child_kinds = [c.get("kind", "").lower() for c in child_list]
        groups[label] = child_kinds

    infra_kinds = groups.get("infrastructure", [])
    org_kinds = groups.get("organization", [])

    issues = []
    for expected in ["dcimserver", "dcimswitch", "dcimpdu"]:
        if not any(expected in k for k in infra_kinds):
            issues.append(f"{expected} not under Infrastructure")
    for expected in ["organizationmanufacturer", "organizationprovider"]:
        if not any(expected in k for k in org_kinds):
            issues.append(f"{expected} not under Organization")

    if issues:
        return False, "; ".join(issues)
    return True, "Correct grouping: infra and org items under right headers"


def check_all_nodes_present(doc: dict, **_) -> tuple[bool, str]:
    expected = {"DcimServer", "DcimSwitch", "DcimPdu",
                "OrganizationManufacturer", "OrganizationProvider"}
    found = set()
    for item in _all_menu_items_recursive(doc):
        kind = item.get("kind", "")
        if kind in expected:
            found.add(kind)
    missing = expected - found
    if missing:
        return False, f"Missing nodes: {', '.join(sorted(missing))}"
    return True, f"All {len(expected)} nodes present"


def check_contextual_icons(doc: dict, **_) -> tuple[bool, str]:
    for item in _all_menu_items_recursive(doc):
        icon = item.get("icon", "")
        if not icon.startswith("mdi:"):
            return False, f"{item.get('name', '?')} icon missing mdi: prefix"
    # If all have mdi: icons, consider them contextual (basic check)
    items = _all_menu_items_recursive(doc)
    if not items:
        return False, "No menu items found"
    return True, f"All {len(items)} items have mdi: icons"


def check_generic_kind_link(doc: dict, **_) -> tuple[bool, str]:
    for item in _all_menu_items_recursive(doc):
        kind = item.get("kind", "")
        if "generic" in kind.lower() or kind == "LocationGeneric":
            return True, f"Item {item.get('name', '?')} uses kind: {kind}"
    return False, "No menu item with kind referencing a Generic"


def check_location_children(doc: dict, **_) -> tuple[bool, str]:
    location_types = {"region", "site", "room", "rack"}
    found = set()
    for item in _all_menu_items_recursive(doc):
        kind = (item.get("kind") or "").lower()
        name = (item.get("name") or "").lower()
        for loc in location_types:
            if loc in kind or loc in name:
                found.add(loc)
    missing = location_types - found
    if missing:
        return False, f"Missing location children: {', '.join(sorted(missing))}"
    return True, "All location types present as children"


def check_separate_devices_section(doc: dict, **_) -> tuple[bool, str]:
    for item in _menu_items(doc):
        label = (item.get("label") or item.get("name") or "").lower()
        kind = (item.get("kind") or "").lower()
        children = item.get("children", {})
        child_list = children.get("data", []) if isinstance(children, dict) else children if isinstance(children, list) else []
        child_kinds = [(c.get("kind") or "").lower() for c in child_list]
        if "device" in label or "device" in kind or any("device" in k for k in child_kinds):
            # Check it's not under a locations group
            if "location" not in label:
                return True, f"Devices found in separate section: {item.get('label', item.get('name'))}"
    return False, "No separate devices section found"


def check_include_in_menu_false(doc: dict, raw_text: str = "", **_) -> tuple[bool, str]:
    # This advice would normally be in the text output, not in the YAML.
    # Check if it appears as a YAML comment in the output file.
    if "include_in_menu" in raw_text:
        return True, "include_in_menu mentioned in output"
    return False, "No mention of include_in_menu in output"


def check_infrahub_yml_registration(doc: dict, raw_text: str = "", **_) -> tuple[bool, str]:
    if ".infrahub.yml" in raw_text or "infrahub.yml" in raw_text:
        return True, ".infrahub.yml registration mentioned in output"
    return False, "No mention of .infrahub.yml registration in output"


def check_schema_comment(doc: dict, raw_text: str = "", **_) -> tuple[bool, str]:
    if "$schema" in raw_text or "yaml-language-server" in raw_text:
        return True, "$schema comment found in raw YAML"
    return False, "No $schema or yaml-language-server comment found"


def check_generic_rel_inline_data(doc: dict, **_) -> tuple[bool, str]:
    """Check location relationships use inline data blocks with kind and data keys."""
    if not doc:
        return False, "Empty document"
    data_items = doc.get("spec", {}).get("data", [])
    if not data_items:
        return False, "No data items in spec.data"
    for item in data_items:
        loc = item.get("location")
        if loc is None:
            continue  # No location is fine (e.g., prefix without location)
        if not isinstance(loc, dict):
            return False, f"location is a {type(loc).__name__}, expected inline data block"
        if "kind" not in loc:
            return False, "location inline block missing 'kind' key"
        if "data" not in loc or not isinstance(loc["data"], list) or len(loc["data"]) == 0:
            return False, "location inline block missing or empty 'data' list"
    return True, "All location references use inline data blocks with kind and data"


def check_no_scalar_location(doc: dict, **_) -> tuple[bool, str]:
    """Ensure no location value is a plain string scalar."""
    if not doc:
        return False, "Empty document"
    data_items = doc.get("spec", {}).get("data", [])
    for item in data_items:
        loc = item.get("location")
        if isinstance(loc, str):
            return False, f"Found scalar location: '{loc}'"
    return True, "No scalar location values found"


def check_all_prefixes_present(doc: dict, **_) -> tuple[bool, str]:
    """Check all three expected prefixes are present."""
    expected = {"10.0.0.0/24", "10.1.0.0/24", "10.2.0.0/24"}
    found = set()
    if not doc:
        return False, "Empty document"
    data_items = doc.get("spec", {}).get("data", [])
    for item in data_items:
        p = item.get("prefix")
        if p and str(p) in expected:
            found.add(str(p))
    missing = expected - found
    if missing:
        return False, f"Missing prefixes: {missing}"
    return True, f"All {len(expected)} prefixes found"


def check_null_location_handled(doc: dict, **_) -> tuple[bool, str]:
    """Check the prefix without location handles it correctly."""
    if not doc:
        return False, "Empty document"
    data_items = doc.get("spec", {}).get("data", [])
    for item in data_items:
        if str(item.get("prefix", "")) == "10.2.0.0/24":
            loc = item.get("location")
            if loc is None:
                return True, "Locationless prefix has null/omitted location"
            if isinstance(loc, str) and loc == "":
                return True, "Locationless prefix has empty string location"
            return False, f"Locationless prefix has unexpected location: {loc}"
    return False, "Prefix 10.2.0.0/24 not found"


# Map assertion names to check functions
ASSERTION_CHECKS = {
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
    # Menu-creator assertions
    "apiversion-and-kind": check_apiversion_and_kind,
    "spec-data-structure": check_spec_data_structure,
    "name-and-namespace": check_name_and_namespace,
    "kind-for-schema-links": check_kind_for_schema_links,
    "mdi-icons": check_mdi_icons,
    "labels-present": check_labels_present,
    "group-headers-no-kind": check_group_headers_no_kind,
    "children-data-wrapper": check_children_data_wrapper,
    "leaf-items-have-kind": check_leaf_items_have_kind,
    "correct-grouping": check_correct_grouping,
    "all-nodes-present": check_all_nodes_present,
    "contextual-icons": check_contextual_icons,
    "generic-kind-link": check_generic_kind_link,
    "location-children": check_location_children,
    "separate-devices-section": check_separate_devices_section,
    "include-in-menu-false": check_include_in_menu_false,
    "infrahub-yml-registration": check_infrahub_yml_registration,
    "schema-comment": check_schema_comment,
    # Object-creator assertions
    "generic-rel-inline-data": check_generic_rel_inline_data,
    "no-scalar-location": check_no_scalar_location,
    "all-prefixes-present": check_all_prefixes_present,
    "null-location-handled": check_null_location_handled,
}


def grade_schema(schema_path: Path, assertions: list[dict]) -> dict:
    """Grade a YAML output file against a list of assertions."""
    try:
        raw_text = schema_path.read_text()
        schema = yaml.safe_load(raw_text)
    except Exception as e:
        return {
            "expectations": [
                {"text": a.get("check", "<missing check>"), "passed": False, "evidence": f"Failed to load schema: {e}"}
                for a in assertions
            ],
            "summary": {"passed": 0, "failed": len(assertions), "total": len(assertions), "pass_rate": 0.0},
        }

    expectations = []
    passed_count = 0
    for assertion in assertions:
        name = assertion["name"]
        check_fn = ASSERTION_CHECKS.get(name)
        if check_fn:
            ok, evidence = check_fn(schema, raw_text=raw_text)
        else:
            ok, evidence = False, f"No check function for assertion '{name}'"

        expectations.append({"text": assertion["check"], "passed": ok, "evidence": evidence})
        if ok:
            passed_count += 1

    total = len(assertions)
    return {
        "expectations": expectations,
        "summary": {
            "passed": passed_count,
            "failed": total - passed_count,
            "total": total,
            "pass_rate": round(passed_count / total, 3) if total else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_benchmark(eval_results: list[dict], skill_name: str, model: str) -> dict:
    """Build benchmark.json from eval results."""
    runs = []
    rates, times, tokens = [], [], []

    for er in eval_results:
        grading = er["grading"]
        timing = er.get("timing", {})
        run = {
            "eval_id": er["eval_id"],
            "eval_name": er["eval_name"],
            "result": {
                "pass_rate": grading["summary"]["pass_rate"],
                "passed": grading["summary"]["passed"],
                "failed": grading["summary"]["failed"],
                "total": grading["summary"]["total"],
                "time_seconds": timing.get("total_duration_seconds", 0),
                "tokens": timing.get("total_tokens", 0),
            },
            "expectations": grading["expectations"],
        }
        runs.append(run)
        rates.append(grading["summary"]["pass_rate"])
        times.append(timing.get("total_duration_seconds", 0))
        tokens.append(timing.get("total_tokens", 0))

    def _stats(vals):
        if not vals:
            return {"mean": 0, "stddev": 0}
        n = len(vals)
        mean = sum(vals) / n
        std = (sum((v - mean) ** 2 for v in vals) / (n - 1)) ** 0.5 if n > 1 else 0
        return {"mean": round(mean, 3), "stddev": round(std, 3)}

    return {
        "metadata": {
            "skill_name": skill_name,
            "executor_model": model,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": [er["eval_id"] for er in eval_results],
        },
        "runs": runs,
        "summary": {
            "pass_rate": _stats(rates),
            "time_seconds": _stats(times),
            "tokens": _stats(tokens),
        },
    }


def generate_markdown_report(benchmark: dict) -> str:
    """Generate a Markdown report from benchmark data."""
    meta = benchmark["metadata"]
    summary = benchmark["summary"]

    lines = [
        f"# Skill Eval: {meta['skill_name']}",
        "",
        f"**Model:** {meta['executor_model']}  "
        f"**Date:** {meta['timestamp']}  "
        f"**Pass Rate:** {summary['pass_rate']['mean']*100:.0f}%",
        "",
    ]

    for run in benchmark["runs"]:
        eval_name = run.get("eval_name", f"eval-{run['eval_id']}")
        r = run["result"]
        status = "✅" if r["pass_rate"] == 1.0 else "⚠️" if r["pass_rate"] >= 0.5 else "❌"
        lines.append(f"### {status} {eval_name} — {r['passed']}/{r['total']}")
        lines.append("")

        for exp in run["expectations"]:
            icon = "✅" if exp["passed"] else "❌"
            lines.append(f"- {icon} {exp['text'][:80]}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run skill evaluations")
    parser.add_argument(
        "--eval-file", type=Path, default=None,
        help="Path to eval JSON file (default: all files in evaluations/)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("eval-results"),
        help="Directory to store results (default: eval-results)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model to use for claude -p (default: CLI default)",
    )
    parser.add_argument(
        "--skip-baseline", action="store_true",
        help="Skip running without-skill baseline",
    )
    args = parser.parse_args()

    # Discover eval files
    if args.eval_file:
        eval_files = [args.eval_file]
    else:
        eval_dir = REPO_ROOT / "evaluations"
        eval_files = sorted(eval_dir.glob("*.json"))

    if not eval_files:
        print("No evaluation files found.")
        sys.exit(1)

    output_base = REPO_ROOT / args.output_dir
    output_base.mkdir(parents=True, exist_ok=True)

    all_results = []

    for eval_file in eval_files:
        print(f"\n{'='*60}")
        print(f"Processing: {eval_file.name}")
        print(f"{'='*60}")

        with open(eval_file) as f:
            eval_data = json.load(f)

        skill_name = eval_data["skill_name"]
        skill_path = SKILL_PATHS.get(skill_name)
        if not skill_path:
            print(f"  WARNING: No skill path for '{skill_name}', skipping")
            continue

        for ev in eval_data["evals"]:
            eval_id = ev["id"]
            eval_name = ev.get("prompt", "")[:40].replace(" ", "-").lower()
            eval_name = f"eval-{eval_id}"
            eval_dir = output_base / skill_name / eval_name

            print(f"\n  Eval {eval_id}: {ev['prompt'][:80]}...")

            # Run with skill
            print(f"    Running with skill...")
            ws_dir = eval_dir / "with_skill" / "outputs"
            ws_timing = run_claude_prompt(
                ev["prompt"], ws_dir, with_skill=True,
                skill_path=skill_path, model=args.model,
            )
            print(f"    Done ({ws_timing['total_duration_seconds']}s, {ws_timing['total_tokens']} tokens)")

            # Run without skill
            wos_timing = {"total_tokens": 0, "duration_ms": 0, "total_duration_seconds": 0}
            if not args.skip_baseline:
                print(f"    Running without skill (baseline)...")
                wos_dir = eval_dir / "without_skill" / "outputs"
                wos_timing = run_claude_prompt(
                    ev["prompt"], wos_dir, with_skill=False, model=args.model,
                )
                print(f"    Done ({wos_timing['total_duration_seconds']}s, {wos_timing['total_tokens']} tokens)")

            # Grade outputs
            assertions = ev.get("assertions", [])
            ws_schema = eval_dir / "with_skill" / "outputs" / "schema.yml"
            wos_schema = eval_dir / "without_skill" / "outputs" / "schema.yml"

            print(f"    Grading...")
            ws_grading = grade_schema(ws_schema, assertions) if ws_schema.exists() else {
                "expectations": [{"text": a.get("check", "<missing check>"), "passed": False, "evidence": "No schema file produced"} for a in assertions],
                "summary": {"passed": 0, "failed": len(assertions), "total": len(assertions), "pass_rate": 0.0},
            }

            wos_grading = {"expectations": [], "summary": {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0}}
            if not args.skip_baseline and wos_schema.exists():
                wos_grading = grade_schema(wos_schema, assertions)
            elif not args.skip_baseline:
                wos_grading = {
                    "expectations": [{"text": a.get("check", "<missing check>"), "passed": False, "evidence": "No schema file produced"} for a in assertions],
                    "summary": {"passed": 0, "failed": len(assertions), "total": len(assertions), "pass_rate": 0.0},
                }

            # Save grading
            with open(eval_dir / "with_skill" / "grading.json", "w") as f:
                json.dump(ws_grading, f, indent=2)
            if not args.skip_baseline:
                (eval_dir / "without_skill").mkdir(parents=True, exist_ok=True)
                with open(eval_dir / "without_skill" / "grading.json", "w") as f:
                    json.dump(wos_grading, f, indent=2)

            ws_pass = ws_grading["summary"]["pass_rate"]
            wos_pass = wos_grading["summary"]["pass_rate"]
            print(f"    With skill: {ws_grading['summary']['passed']}/{ws_grading['summary']['total']} ({ws_pass*100:.0f}%)")
            if not args.skip_baseline:
                print(f"    Without skill: {wos_grading['summary']['passed']}/{wos_grading['summary']['total']} ({wos_pass*100:.0f}%)")

            all_results.append({
                "eval_id": eval_id,
                "eval_name": eval_name,
                "skill_name": skill_name,
                "with_skill": {"grading": ws_grading, "timing": ws_timing},
                "without_skill": {"grading": wos_grading, "timing": wos_timing},
            })

    # Generate benchmark
    model_label = args.model or "default"
    for eval_file in eval_files:
        with open(eval_file) as f:
            skill_name = json.load(f)["skill_name"]

        skill_results = [r for r in all_results if r.get("skill_name") == skill_name]
        if not skill_results:
            continue

        benchmark = build_benchmark(skill_results, skill_name, model_label)
        benchmark_path = output_base / skill_name
        benchmark_path.mkdir(parents=True, exist_ok=True)

        with open(benchmark_path / "benchmark.json", "w") as f:
            json.dump(benchmark, f, indent=2)

        report = generate_markdown_report(benchmark)
        with open(benchmark_path / "report.md", "w") as f:
            f.write(report)

        # Also write to the top-level output dir for easy artifact access
        with open(output_base / "benchmark.json", "w") as f:
            json.dump(benchmark, f, indent=2)
        with open(output_base / "report.md", "w") as f:
            f.write(report)

        print(f"\n{'='*60}")
        print(f"RESULTS: {skill_name}")
        print(f"{'='*60}")
        print(report)

    # Exit with failure if any with_skill pass rate is below threshold
    has_failure = False
    for r in all_results:
        if r["with_skill"]["grading"]["summary"]["pass_rate"] < 0.5:
            print(f"\nFAILURE: Eval {r['eval_id']} with-skill pass rate below 50%")
            has_failure = True
    if has_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
