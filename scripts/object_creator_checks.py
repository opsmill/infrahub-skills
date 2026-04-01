#!/usr/bin/env python3
"""
Object-creator assertion checks for skill evaluations.

Follows the conventions from dga-20260318-testing-framework: each check
function takes (doc: dict, **_) where doc is the parsed YAML output,
and returns (bool, str).

These checks validate that generic relationship references use inline
data blocks with explicit kind: instead of scalar HFID references.
"""

try:
    import yaml  # noqa: F401
except ImportError:
    pass


# ---------------------------------------------------------------------------
# SKILL_PATHS — add object-creator alongside existing entries
# ---------------------------------------------------------------------------

SKILL_PATHS_OBJECT_CREATOR = {
    "infrahub-object-creator": "skills/infrahub-object-creator/SKILL.md",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spec_data(doc: dict) -> list[dict]:
    """Return spec.data items from an Object document."""
    return doc.get("spec", {}).get("data", []) or []


# ---------------------------------------------------------------------------
# Object-creator assertion checks
#
# Each function takes (doc: dict, **_) and returns (bool, str).
# ---------------------------------------------------------------------------


def check_generic_rel_inline_data(doc: dict, **_: object) -> tuple[bool, str]:
    """Check location relationships use inline data blocks with kind and data keys."""
    data_items = _spec_data(doc)
    if not data_items:
        return False, "No spec.data items found"
    for item in data_items:
        loc = item.get("location")
        if loc is None:
            continue  # No location is fine
        if not isinstance(loc, dict):
            return False, f"location is a {type(loc).__name__}, not an inline data block"
        if "kind" not in loc:
            return False, "location inline block missing 'kind' key"
        if "data" not in loc or not isinstance(loc["data"], list) or len(loc["data"]) == 0:
            return False, "location inline block missing or empty 'data' list"
    return True, "All location references use inline data blocks with kind and data"


def check_object_apiversion_and_kind(doc: dict, **_: object) -> tuple[bool, str]:
    """Check file has apiVersion: infrahub.app/v1 and kind: Object."""
    api = doc.get("apiVersion")
    kind = doc.get("kind")
    if api == "infrahub.app/v1" and kind == "Object":
        return True, "apiVersion: infrahub.app/v1 and kind: Object"
    return False, f"apiVersion: {api}, kind: {kind}"


def check_no_scalar_location(doc: dict, **_: object) -> tuple[bool, str]:
    """Ensure no location value is a plain string scalar."""
    data_items = _spec_data(doc)
    for item in data_items:
        loc = item.get("location")
        if isinstance(loc, str):
            return False, f"Found scalar location: '{loc}'"
    return True, "No scalar location values found"


def check_all_prefixes_present(doc: dict, **_: object) -> tuple[bool, str]:
    """Check all three expected prefixes are present."""
    expected = {"10.0.0.0/24", "10.1.0.0/24", "10.2.0.0/24"}
    found: set[str] = set()
    data_items = _spec_data(doc)
    for item in data_items:
        p = item.get("prefix")
        if p and str(p) in expected:
            found.add(str(p))
    missing = expected - found
    if missing:
        return False, f"Missing prefixes: {missing}"
    return True, f"All {len(expected)} prefixes found"


def check_null_location_handled(doc: dict, **_: object) -> tuple[bool, str]:
    """Check the prefix without location handles it correctly."""
    data_items = _spec_data(doc)
    for item in data_items:
        if item.get("prefix") == "10.2.0.0/24":
            loc = item.get("location")
            if loc is None or loc == "" or "location" not in item:
                return True, "Locationless prefix has null/omitted location"
            return False, f"Locationless prefix has location: {loc}"
    return False, "Prefix 10.2.0.0/24 not found"


# ---------------------------------------------------------------------------
# Registry — to be merged into ASSERTION_CHECKS in run_evals.py from
# dga-20260318-testing-framework
# ---------------------------------------------------------------------------

OBJECT_CREATOR_CHECKS = {
    "generic-rel-inline-data": check_generic_rel_inline_data,
    "object-apiversion-and-kind": check_object_apiversion_and_kind,
    "no-scalar-location": check_no_scalar_location,
    "all-prefixes-present": check_all_prefixes_present,
    "null-location-handled": check_null_location_handled,
}
