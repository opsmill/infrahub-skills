"""Shared grader library for infrahub-managing-menus skill evaluations.

Provides YAML parsing helpers, individual assertion check functions, a CHECKS
registry, and the top-level ``run_checks`` function that returns skillgrade
JSON format.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["apiversion-and-kind", "spec-data-structure", "name-and-namespace"],
        Path("outputs/task-1/menu.yml"),
    )
    print(result)  # {"score": 0.67, "details": "...", "checks": [...]}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# Low-level menu traversal helpers
# ---------------------------------------------------------------------------


def _menu_items(doc: dict) -> list[dict]:
    """Return top-level menu items from spec.data."""
    return doc.get("spec", {}).get("data", []) or []


def _all_menu_leaves(doc: dict) -> list[dict]:
    """Recursively collect all leaf menu items (items with a 'kind' key)."""
    leaves: list[dict] = []

    def _walk(items: list) -> None:
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
    items: list[dict] = []

    def _walk(item_list: list) -> None:
        for item in (item_list or []):
            items.append(item)
            children = item.get("children", {})
            if isinstance(children, dict):
                _walk(children.get("data", []))
            elif isinstance(children, list):
                _walk(children)

    _walk(_menu_items(doc))
    return items


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output(path: Path) -> tuple[dict, str]:
    """Load a YAML menu file and return ``(parsed_dict, raw_text)``.

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
#     check_*(doc: dict, **kwargs) -> tuple[bool, str]
#
# where the bool is True on pass, and str is a human-readable message.
# ---------------------------------------------------------------------------


def check_apiversion_and_kind(doc: dict, **_: Any) -> tuple[bool, str]:
    """apiVersion: infrahub.app/v1 and kind: Menu."""
    api = doc.get("apiVersion")
    kind = doc.get("kind")
    if api == "infrahub.app/v1" and kind == "Menu":
        return True, "apiVersion: infrahub.app/v1 and kind: Menu"
    return False, f"apiVersion: {api}, kind: {kind}"


def check_spec_data_structure(doc: dict, **_: Any) -> tuple[bool, str]:
    """Items under spec.data as list."""
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        return False, "No spec key or spec is not a dict"
    data = spec.get("data")
    if not isinstance(data, list):
        return False, f"spec.data is {type(data).__name__}, expected list"
    if len(data) == 0:
        return False, "spec.data is empty"
    return True, f"spec.data is a list with {len(data)} items"


def check_name_and_namespace(doc: dict, **_: Any) -> tuple[bool, str]:
    """Every item has name and namespace."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    missing: list[str] = []
    for item in all_items:
        label = item.get("label", item.get("name", "?"))
        if not item.get("name"):
            missing.append(f"{label} missing name")
        if not item.get("namespace"):
            missing.append(f"{label} missing namespace")
    if missing:
        return False, f"Issues: {', '.join(missing)}"
    return True, "All items have name and namespace"


def check_kind_for_schema_links(doc: dict, **_: Any) -> tuple[bool, str]:
    """Items use kind, not path."""
    leaves = _all_menu_leaves(doc)
    if not leaves:
        return False, "No leaf items with kind found"
    for item in leaves:
        if item.get("path") and not item.get("kind"):
            return False, f"Item {item.get('name')} uses path instead of kind"
    return True, f"{len(leaves)} items use kind for schema links"


def check_mdi_icons(doc: dict, **_: Any) -> tuple[bool, str]:
    """All icons use mdi: prefix."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    bad: list[str] = []
    for item in all_items:
        icon = item.get("icon", "")
        if not icon:
            bad.append(f"{item.get('name', '?')} has no icon")
        elif not icon.startswith("mdi:"):
            bad.append(f"{item.get('name', '?')} icon '{icon}' missing mdi: prefix")
    if bad:
        return False, f"Icon issues: {', '.join(bad)}"
    return True, "All icons use mdi: prefix"


def check_labels_present(doc: dict, **_: Any) -> tuple[bool, str]:
    """Each item has label."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    missing: list[str] = []
    for item in all_items:
        if not item.get("label"):
            missing.append(item.get("name", "?"))
    if missing:
        return False, f"Missing label on: {', '.join(missing)}"
    return True, "All items have labels"


def check_group_headers_no_kind(doc: dict, **_: Any) -> tuple[bool, str]:
    """Group headers have no kind/path."""
    groups = [
        i for i in _menu_items(doc)
        if i.get("children") and not i.get("kind") and not i.get("path")
    ]
    if not groups:
        return False, "No top-level group headers without kind/path found"
    bad = [
        g.get("name", "?") for g in _menu_items(doc)
        if g.get("children") and (g.get("kind") or g.get("path"))
    ]
    if bad:
        return False, f"Group headers with kind/path: {', '.join(bad)}"
    return True, f"{len(groups)} group headers without kind/path"


def check_children_data_wrapper(doc: dict, **_: Any) -> tuple[bool, str]:
    """Children use children.data wrapper."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    for item in all_items:
        children = item.get("children")
        if children is None:
            continue
        if isinstance(children, list):
            return (
                False,
                f"Item {item.get('name', '?')} has children as a list, "
                f"expected children.data wrapper",
            )
        if isinstance(children, dict) and "data" in children:
            continue
        return False, f"Item {item.get('name', '?')} has children but no data key"
    return True, "All children use children.data wrapper"


def check_leaf_items_have_kind(doc: dict, **_: Any) -> tuple[bool, str]:
    """Leaf items use kind."""
    leaves = _all_menu_leaves(doc)
    if not leaves:
        # Check if there are any items without children that also lack kind
        for item in _all_menu_items_recursive(doc):
            if not item.get("children") and not item.get("kind"):
                return False, f"Leaf item {item.get('name', '?')} has no kind"
        return False, "No leaf items found"
    return True, f"{len(leaves)} leaf items have kind"


def check_correct_grouping(doc: dict, **_: Any) -> tuple[bool, str]:
    """Server/Switch/PDU under Infrastructure, Manufacturer/Provider under Organization."""
    groups: dict[str, list[str]] = {}
    for item in _menu_items(doc):
        label = (item.get("label") or item.get("name") or "").lower()
        children = item.get("children", {})
        if isinstance(children, dict):
            child_list = children.get("data", [])
        elif isinstance(children, list):
            child_list = children
        else:
            child_list = []
        child_kinds = [c.get("kind", "").lower() for c in child_list]
        groups[label] = child_kinds

    infra_kinds = groups.get("infrastructure", [])
    org_kinds = groups.get("organization", [])

    issues: list[str] = []
    for expected in ["dcimserver", "dcimswitch", "dcimpdu"]:
        if not any(expected in k for k in infra_kinds):
            issues.append(f"{expected} not under Infrastructure")
    for expected in ["organizationmanufacturer", "organizationprovider"]:
        if not any(expected in k for k in org_kinds):
            issues.append(f"{expected} not under Organization")

    if issues:
        return False, "; ".join(issues)
    return True, "Correct grouping: infra and org items under right headers"


def check_all_nodes_present(doc: dict, **_: Any) -> tuple[bool, str]:
    """All 5 nodes present."""
    expected = {
        "DcimServer",
        "DcimSwitch",
        "DcimPdu",
        "OrganizationManufacturer",
        "OrganizationProvider",
    }
    found: set[str] = set()
    for item in _all_menu_items_recursive(doc):
        kind = item.get("kind", "")
        if kind in expected:
            found.add(kind)
    missing = expected - found
    if missing:
        return False, f"Missing nodes: {', '.join(sorted(missing))}"
    return True, f"All {len(expected)} nodes present"


def check_contextual_icons(doc: dict, **_: Any) -> tuple[bool, str]:
    """Icons are contextually appropriate (mdi: prefix)."""
    for item in _all_menu_items_recursive(doc):
        icon = item.get("icon", "")
        if not icon.startswith("mdi:"):
            return False, f"{item.get('name', '?')} icon missing mdi: prefix"
    items = _all_menu_items_recursive(doc)
    if not items:
        return False, "No menu items found"
    return True, f"All {len(items)} items have mdi: icons"


def check_generic_kind_link(doc: dict, **_: Any) -> tuple[bool, str]:
    """Menu item uses kind: LocationGeneric."""
    for item in _all_menu_items_recursive(doc):
        kind = item.get("kind", "")
        if "generic" in kind.lower() or kind == "LocationGeneric":
            return True, f"Item {item.get('name', '?')} uses kind: {kind}"
    return False, "No menu item with kind referencing a Generic"


def check_location_children(doc: dict, **_: Any) -> tuple[bool, str]:
    """Individual location types as children."""
    location_types = {"region", "site", "room", "rack"}
    found: set[str] = set()
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


def check_separate_devices_section(doc: dict, **_: Any) -> tuple[bool, str]:
    """Devices separate from Locations."""
    for item in _menu_items(doc):
        label = (item.get("label") or item.get("name") or "").lower()
        kind = (item.get("kind") or "").lower()
        children = item.get("children", {})
        if isinstance(children, dict):
            child_list = children.get("data", [])
        elif isinstance(children, list):
            child_list = children
        else:
            child_list = []
        child_kinds = [(c.get("kind") or "").lower() for c in child_list]
        if "device" in label or "device" in kind or any("device" in k for k in child_kinds):
            # Check it's not under a locations group
            if "location" not in label:
                return (
                    True,
                    f"Devices found in separate section: {item.get('label', item.get('name'))}",
                )
    return False, "No separate devices section found"


def check_include_in_menu_false(doc: dict, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Advises include_in_menu: false (checks raw text)."""
    if "include_in_menu" in raw_text:
        return True, "include_in_menu mentioned in output"
    return False, "No mention of include_in_menu in output"


def check_infrahub_yml_registration(doc: dict, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Mentions .infrahub.yml (checks raw text)."""
    if ".infrahub.yml" in raw_text or "infrahub.yml" in raw_text:
        return True, ".infrahub.yml registration mentioned in output"
    return False, "No mention of .infrahub.yml registration in output"


def check_schema_comment(doc: dict, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Has $schema or yaml-language-server comment (checks raw text)."""
    if "$schema" in raw_text or "yaml-language-server" in raw_text:
        return True, "$schema comment found in raw YAML"
    return False, "No $schema or yaml-language-server comment found"


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
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
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_path: Path,
    raw_text: str | None = None,
) -> dict:
    """Run named checks against a menu YAML file and return skillgrade JSON.

    Parameters
    ----------
    check_names:
        List of assertion names from the ``CHECKS`` registry.
    output_path:
        Path to the menu YAML file produced by the model.
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
    doc, file_raw = load_output(output_path)
    if raw_text is None:
        raw_text = file_raw

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            ok, msg = fn(doc, raw_text=raw_text)
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
