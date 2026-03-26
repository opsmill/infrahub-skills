"""Tests for skills/schema-creator/graders/lib.py.

Covers >= 10 check functions against both good and bad schemas.
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Adjust import path so tests work when run from repo root or this directory.
# The grader library lives in skills/schema-creator/graders/lib.py — the
# hyphenated directory name is not a valid Python package name so we use
# importlib.util to load the module directly by file path.
# ---------------------------------------------------------------------------
import importlib.util
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "skills" / "schema-creator" / "graders" / "lib.py"
_spec = importlib.util.spec_from_file_location("schema_creator_graders_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CHECKS = _mod.CHECKS
_all_attrs = _mod._all_attrs
_all_generics = _mod._all_generics
_all_nodes = _mod._all_nodes
_all_rels = _mod._all_rels
_full_kind = _mod._full_kind
check_attr_min_length = _mod.check_attr_min_length
check_attribute_kind_relationships = _mod.check_attribute_kind_relationships
check_correct_hierarchy_chain = _mod.check_correct_hierarchy_chain
check_display_label_singular = _mod.check_display_label_singular
check_dropdown_for_status = _mod.check_dropdown_for_status
check_endpoint_device_relationship = _mod.check_endpoint_device_relationship
check_full_kind_references = _mod.check_full_kind_references
check_hierarchical_generic = _mod.check_hierarchical_generic
check_human_friendly_id = _mod.check_human_friendly_id
check_inherit_from_generic = _mod.check_inherit_from_generic
check_matching_identifiers = _mod.check_matching_identifiers
check_no_deprecated_string = _mod.check_no_deprecated_string
check_root_no_parent = _mod.check_root_no_parent
check_schema_version = _mod.check_schema_version
check_two_endpoint_relationships = _mod.check_two_endpoint_relationships
load_output = _mod.load_output
run_checks = _mod.run_checks


# ---------------------------------------------------------------------------
# Minimal valid schema fixtures
# ---------------------------------------------------------------------------

GOOD_SIMPLE_SCHEMA = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Device",
            "namespace": "Infra",
            "display_label": "{{ name__value }}",
            "human_friendly_id": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "status", "kind": "Dropdown", "choices": [
                    {"name": "active", "label": "Active"},
                    {"name": "inactive", "label": "Inactive"},
                ]},
            ],
            "relationships": [],
        }
    ],
    "generics": [],
}

GOOD_SCHEMA_WITH_GENERIC = {
    "version": "1.0",
    "generics": [
        {
            "name": "Location",
            "namespace": "Loc",
            "hierarchical": True,
            "display_label": "{{ name__value }}",
            "human_friendly_id": ["name__value"],
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [],
        }
    ],
    "nodes": [
        {
            "name": "Region",
            "namespace": "Loc",
            "inherit_from": ["LocLocation"],
            "parent": "",
            "children": "LocSite",
            "attributes": [],
            "relationships": [],
        },
        {
            "name": "Site",
            "namespace": "Loc",
            "inherit_from": ["LocLocation"],
            "parent": "LocRegion",
            "children": "LocRoom",
            "attributes": [],
            "relationships": [],
        },
        {
            "name": "Room",
            "namespace": "Loc",
            "inherit_from": ["LocLocation"],
            "parent": "LocSite",
            "children": "LocRack",
            "attributes": [],
            "relationships": [],
        },
        {
            "name": "Rack",
            "namespace": "Loc",
            "inherit_from": ["LocLocation"],
            "parent": "LocRoom",
            "children": "",
            "attributes": [],
            "relationships": [],
        },
    ],
}

GOOD_CIRCUIT_SCHEMA = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Circuit",
            "namespace": "Net",
            "display_label": "{{ circuit_id__value }}",
            "human_friendly_id": ["circuit_id__value"],
            "attributes": [{"name": "circuit_id", "kind": "Text"}],
            "relationships": [
                {
                    "name": "provider",
                    "peer": "OrganizationProvider",
                    "kind": "Attribute",
                    "identifier": "circuit__provider",
                },
                {
                    "name": "endpoint_a",
                    "peer": "NetCircuitEndpoint",
                    "kind": "Component",
                    "identifier": "circuit__endpoints",
                },
                {
                    "name": "endpoint_z",
                    "peer": "NetCircuitEndpoint",
                    "kind": "Component",
                    "identifier": "circuit__endpoints",
                },
            ],
        },
        {
            "name": "CircuitEndpoint",
            "namespace": "Net",
            "display_label": "{{ name__value }}",
            "human_friendly_id": ["name__value"],
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {
                    "name": "circuit",
                    "peer": "NetCircuit",
                    "kind": "Parent",
                    "identifier": "circuit__endpoints",
                },
                {
                    "name": "device",
                    "peer": "InfraDevice",
                    "kind": "Attribute",
                    "identifier": "endpoint__device",
                },
            ],
        },
    ],
    "generics": [],
}


# ---------------------------------------------------------------------------
# Helper functions tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_all_nodes(self):
        assert _all_nodes(GOOD_SIMPLE_SCHEMA) == GOOD_SIMPLE_SCHEMA["nodes"]

    def test_all_generics(self):
        assert _all_generics(GOOD_SCHEMA_WITH_GENERIC) == GOOD_SCHEMA_WITH_GENERIC["generics"]

    def test_all_attrs(self):
        node = GOOD_SIMPLE_SCHEMA["nodes"][0]
        assert _all_attrs(node) == node["attributes"]

    def test_all_rels(self):
        node = GOOD_SIMPLE_SCHEMA["nodes"][0]
        assert _all_rels(node) == []

    def test_full_kind(self):
        node = {"namespace": "Infra", "name": "Device"}
        assert _full_kind(node) == "InfraDevice"

    def test_full_kind_empty(self):
        assert _full_kind({}) == ""


# ---------------------------------------------------------------------------
# check_schema_version
# ---------------------------------------------------------------------------


class TestCheckSchemaVersion:
    def test_good(self):
        ok, msg = check_schema_version({"version": "1.0"})
        assert ok is True
        assert "1.0" in msg

    def test_bad_missing(self):
        ok, msg = check_schema_version({})
        assert ok is False

    def test_bad_wrong_version(self):
        ok, msg = check_schema_version({"version": "2.0"})
        assert ok is False
        assert "2.0" in msg


# ---------------------------------------------------------------------------
# check_attr_min_length
# ---------------------------------------------------------------------------


class TestCheckAttrMinLength:
    def test_good(self):
        ok, msg = check_attr_min_length(GOOD_SIMPLE_SCHEMA)
        assert ok is True

    def test_bad_short_name(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "attributes": [{"name": "id", "kind": "Text"}],
                }
            ],
            "generics": [],
        }
        ok, msg = check_attr_min_length(schema)
        assert ok is False
        assert "id" in msg

    def test_exactly_three_chars_passes(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "attributes": [{"name": "abc", "kind": "Text"}],
                }
            ],
            "generics": [],
        }
        ok, _ = check_attr_min_length(schema)
        assert ok is True


# ---------------------------------------------------------------------------
# check_dropdown_for_status
# ---------------------------------------------------------------------------


class TestCheckDropdownForStatus:
    def test_good(self):
        ok, msg = check_dropdown_for_status(GOOD_SIMPLE_SCHEMA)
        assert ok is True

    def test_bad_wrong_kind(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "attributes": [{"name": "status", "kind": "Text"}],
                }
            ],
            "generics": [],
        }
        ok, msg = check_dropdown_for_status(schema)
        assert ok is False
        assert "Dropdown" in msg

    def test_bad_no_choices(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "attributes": [{"name": "status", "kind": "Dropdown"}],
                }
            ],
            "generics": [],
        }
        ok, msg = check_dropdown_for_status(schema)
        assert ok is False
        assert "choices" in msg

    def test_bad_no_status_attr(self):
        ok, msg = check_dropdown_for_status({"nodes": [], "generics": []})
        assert ok is False
        assert "No status" in msg


# ---------------------------------------------------------------------------
# check_no_deprecated_string
# ---------------------------------------------------------------------------


class TestCheckNoDeprecatedString:
    def test_good(self):
        ok, _ = check_no_deprecated_string(GOOD_SIMPLE_SCHEMA)
        assert ok is True

    def test_bad_string_kind(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "attributes": [{"name": "name", "kind": "String"}],
                }
            ],
            "generics": [],
        }
        ok, msg = check_no_deprecated_string(schema)
        assert ok is False
        assert "String" in msg


# ---------------------------------------------------------------------------
# check_human_friendly_id
# ---------------------------------------------------------------------------


class TestCheckHumanFriendlyId:
    def test_good_direct(self):
        ok, _ = check_human_friendly_id(GOOD_SIMPLE_SCHEMA)
        assert ok is True

    def test_good_via_generic(self):
        ok, _ = check_human_friendly_id(GOOD_SCHEMA_WITH_GENERIC)
        assert ok is True

    def test_bad_missing(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "attributes": [{"name": "name", "kind": "Text"}],
                }
            ],
            "generics": [],
        }
        ok, msg = check_human_friendly_id(schema)
        assert ok is False
        assert "InfraDevice" in msg


# ---------------------------------------------------------------------------
# check_display_label_singular
# ---------------------------------------------------------------------------


class TestCheckDisplayLabelSingular:
    def test_good(self):
        ok, _ = check_display_label_singular(GOOD_SIMPLE_SCHEMA)
        assert ok is True

    def test_bad_plural_key(self):
        schema = {
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "display_labels": "{{ name__value }}",
                    "attributes": [],
                }
            ],
            "generics": [],
        }
        ok, msg = check_display_label_singular(schema)
        assert ok is False
        assert "plural" in msg.lower() or "display_labels" in msg

    def test_bad_no_label_at_all(self):
        schema = {
            "nodes": [{"name": "Device", "namespace": "Infra", "attributes": []}],
            "generics": [],
        }
        ok, msg = check_display_label_singular(schema)
        assert ok is False
        assert "No display_label" in msg


# ---------------------------------------------------------------------------
# check_full_kind_references
# ---------------------------------------------------------------------------


class TestCheckFullKindReferences:
    def test_good(self):
        ok, _ = check_full_kind_references(GOOD_CIRCUIT_SCHEMA)
        assert ok is True

    def test_bad_short_ref(self):
        schema = {
            "nodes": [
                {
                    "name": "Circuit",
                    "namespace": "Net",
                    "attributes": [],
                    "relationships": [
                        {
                            "name": "endpoint",
                            "peer": "CircuitEndpoint",  # short — no namespace
                            "kind": "Component",
                        }
                    ],
                },
                {
                    "name": "CircuitEndpoint",
                    "namespace": "Net",
                    "attributes": [],
                    "relationships": [],
                },
            ],
            "generics": [],
        }
        ok, msg = check_full_kind_references(schema)
        assert ok is False
        assert "CircuitEndpoint" in msg


# ---------------------------------------------------------------------------
# check_matching_identifiers
# ---------------------------------------------------------------------------


class TestCheckMatchingIdentifiers:
    def test_good(self):
        ok, _ = check_matching_identifiers(GOOD_CIRCUIT_SCHEMA)
        assert ok is True

    def test_bad_orphan_identifier(self):
        schema = {
            "nodes": [
                {
                    "name": "NodeA",
                    "namespace": "Test",
                    "attributes": [],
                    "relationships": [
                        {
                            "name": "rel_to_b",
                            "peer": "TestNodeB",
                            "kind": "Attribute",
                            "identifier": "nodea__nodeb",
                        }
                    ],
                },
                {
                    "name": "NodeB",
                    "namespace": "Test",
                    "attributes": [],
                    "relationships": [
                        {
                            "name": "rel_to_a",
                            "peer": "TestNodeA",
                            "kind": "Attribute",
                            "identifier": "nodea__nodeb_DIFFERENT",  # mismatch
                        }
                    ],
                },
            ],
            "generics": [],
        }
        ok, msg = check_matching_identifiers(schema)
        assert ok is False


# ---------------------------------------------------------------------------
# check_hierarchical_generic
# ---------------------------------------------------------------------------


class TestCheckHierarchicalGeneric:
    def test_good(self):
        ok, msg = check_hierarchical_generic(GOOD_SCHEMA_WITH_GENERIC)
        assert ok is True
        assert "hierarchical" in msg.lower() or "LocLocation" in msg

    def test_bad_no_generic(self):
        ok, msg = check_hierarchical_generic({"nodes": [], "generics": []})
        assert ok is False

    def test_bad_generic_not_hierarchical(self):
        schema = {
            "nodes": [],
            "generics": [{"name": "Location", "namespace": "Loc", "attributes": []}],
        }
        ok, _ = check_hierarchical_generic(schema)
        assert ok is False


# ---------------------------------------------------------------------------
# check_inherit_from_generic
# ---------------------------------------------------------------------------


class TestCheckInheritFromGeneric:
    def test_good(self):
        ok, _ = check_inherit_from_generic(GOOD_SCHEMA_WITH_GENERIC)
        assert ok is True

    def test_bad_node_not_inheriting(self):
        schema = {
            "generics": [
                {
                    "name": "Location",
                    "namespace": "Loc",
                    "hierarchical": True,
                    "attributes": [],
                }
            ],
            "nodes": [
                {
                    "name": "Region",
                    "namespace": "Loc",
                    "inherit_from": [],  # empty — not inheriting
                    "attributes": [],
                    "relationships": [],
                }
            ],
        }
        ok, msg = check_inherit_from_generic(schema)
        assert ok is False
        assert "LocRegion" in msg


# ---------------------------------------------------------------------------
# check_root_no_parent
# ---------------------------------------------------------------------------


class TestCheckRootNoParent:
    def test_good_empty_string(self):
        schema = {
            "nodes": [
                {"name": "Region", "namespace": "Loc", "parent": "", "attributes": []}
            ],
            "generics": [],
        }
        ok, _ = check_root_no_parent(schema)
        assert ok is True

    def test_good_null(self):
        schema = {
            "nodes": [
                {"name": "Region", "namespace": "Loc", "parent": None, "attributes": []}
            ],
            "generics": [],
        }
        ok, _ = check_root_no_parent(schema)
        assert ok is True

    def test_bad_all_have_parents(self):
        schema = {
            "nodes": [
                {"name": "Site", "namespace": "Loc", "parent": "LocRegion", "attributes": []},
                {"name": "Room", "namespace": "Loc", "parent": "LocSite", "attributes": []},
            ],
            "generics": [],
        }
        ok, msg = check_root_no_parent(schema)
        assert ok is False


# ---------------------------------------------------------------------------
# check_correct_hierarchy_chain
# ---------------------------------------------------------------------------


class TestCheckCorrectHierarchyChain:
    def test_good(self):
        ok, msg = check_correct_hierarchy_chain(GOOD_SCHEMA_WITH_GENERIC)
        assert ok is True

    def test_bad_missing_node(self):
        schema = {
            "nodes": [
                {
                    "name": "Region",
                    "namespace": "Loc",
                    "children": "LocSite",
                    "attributes": [],
                }
            ],
            "generics": [],
        }
        ok, msg = check_correct_hierarchy_chain(schema)
        assert ok is False
        assert "site" in msg.lower()


# ---------------------------------------------------------------------------
# check_two_endpoint_relationships
# ---------------------------------------------------------------------------


class TestCheckTwoEndpointRelationships:
    def test_good(self):
        ok, msg = check_two_endpoint_relationships(GOOD_CIRCUIT_SCHEMA)
        assert ok is True
        assert "2" in msg

    def test_bad_no_circuit(self):
        ok, msg = check_two_endpoint_relationships({"nodes": [], "generics": []})
        assert ok is False
        assert "No Circuit" in msg

    def test_bad_one_endpoint(self):
        schema = {
            "nodes": [
                {
                    "name": "Circuit",
                    "namespace": "Net",
                    "attributes": [],
                    "relationships": [
                        {"name": "endpoint_a", "peer": "NetCircuitEndpoint", "kind": "Component"}
                    ],
                }
            ],
            "generics": [],
        }
        ok, msg = check_two_endpoint_relationships(schema)
        assert ok is False
        assert "1" in msg


# ---------------------------------------------------------------------------
# check_attribute_kind_relationships
# ---------------------------------------------------------------------------


class TestCheckAttributeKindRelationships:
    def test_good(self):
        ok, msg = check_attribute_kind_relationships(GOOD_CIRCUIT_SCHEMA)
        assert ok is True

    def test_bad_wrong_kind(self):
        schema = {
            "nodes": [
                {
                    "name": "Circuit",
                    "namespace": "Net",
                    "attributes": [],
                    "relationships": [
                        {
                            "name": "provider",
                            "peer": "OrganizationProvider",
                            "kind": "Generic",  # wrong
                        }
                    ],
                }
            ],
            "generics": [],
        }
        ok, msg = check_attribute_kind_relationships(schema)
        assert ok is False
        assert "Attribute" in msg

    def test_bad_no_provider_rel(self):
        schema = {
            "nodes": [
                {
                    "name": "Circuit",
                    "namespace": "Net",
                    "attributes": [],
                    "relationships": [],
                }
            ],
            "generics": [],
        }
        ok, msg = check_attribute_kind_relationships(schema)
        assert ok is False


# ---------------------------------------------------------------------------
# check_endpoint_device_relationship
# ---------------------------------------------------------------------------


class TestCheckEndpointDeviceRelationship:
    def test_good(self):
        ok, msg = check_endpoint_device_relationship(GOOD_CIRCUIT_SCHEMA)
        assert ok is True

    def test_bad_wrong_kind(self):
        schema = {
            "nodes": [
                {
                    "name": "CircuitEndpoint",
                    "namespace": "Net",
                    "attributes": [],
                    "relationships": [
                        {
                            "name": "device",
                            "peer": "InfraDevice",
                            "kind": "Generic",  # wrong
                        }
                    ],
                }
            ],
            "generics": [],
        }
        ok, msg = check_endpoint_device_relationship(schema)
        assert ok is False
        assert "Attribute" in msg

    def test_bad_no_endpoint(self):
        ok, msg = check_endpoint_device_relationship({"nodes": [], "generics": []})
        assert ok is False
        assert "No Endpoint" in msg


# ---------------------------------------------------------------------------
# Vacuous truth guard clause tests
# ---------------------------------------------------------------------------


class TestVacuousTruthGuards:
    """Checks that iterate over items must not pass vacuously on empty schemas."""

    def test_check_attr_min_length_empty_schema(self):
        ok, msg = check_attr_min_length({})
        assert ok is False
        assert "No nodes or generics found" in msg

    def test_check_no_deprecated_string_empty_schema(self):
        ok, msg = check_no_deprecated_string({})
        assert ok is False
        assert "No nodes or generics found" in msg

    def test_check_full_kind_references_empty_schema(self):
        ok, msg = check_full_kind_references({})
        assert ok is False
        assert "No relationships found" in msg

    def test_check_full_kind_references_no_relationships(self):
        # Nodes exist but have no relationships — still should fail
        schema = {
            "nodes": [{"name": "Device", "namespace": "Infra", "attributes": [], "relationships": []}],
            "generics": [],
        }
        ok, msg = check_full_kind_references(schema)
        assert ok is False
        assert "No relationships found" in msg

    def test_check_human_friendly_id_empty_schema(self):
        ok, msg = check_human_friendly_id({})
        assert ok is False
        assert "No nodes found" in msg


# ---------------------------------------------------------------------------
# load_output
# ---------------------------------------------------------------------------


class TestLoadOutput:
    def test_loads_yaml_file(self, tmp_path):
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text("version: '1.0'\nnodes: []\n")
        schema, raw = load_output(schema_file)
        assert schema["version"] == "1.0"
        assert "version" in raw

    def test_missing_file_returns_empty(self, tmp_path):
        schema, raw = load_output(tmp_path / "nonexistent.yml")
        assert schema == {}
        assert raw == ""


# ---------------------------------------------------------------------------
# CHECKS dict
# ---------------------------------------------------------------------------


class TestChecksDict:
    def test_all_expected_keys_present(self):
        expected = {
            "attr-min-length",
            "dropdown-for-status",
            "no-deprecated-string",
            "full-kind-references",
            "human-friendly-id",
            "display-label-singular",
            "schema-version",
            "matching-identifiers",
            "hierarchical-generic",
            "inherit-from-generic",
            "root-no-parent",
            "correct-hierarchy-chain",
            "two-endpoint-relationships",
            "attribute-kind-relationships",
            "endpoint-device-relationship",
        }
        assert expected.issubset(set(CHECKS.keys()))

    def test_values_are_callable(self):
        for name, fn in CHECKS.items():
            assert callable(fn), f"CHECKS['{name}'] is not callable"


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------


class TestRunChecks:
    def test_returns_skillgrade_format(self, tmp_path):
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text(yaml.dump(GOOD_SIMPLE_SCHEMA))
        result = run_checks(["schema-version", "attr-min-length"], schema_file)
        assert "score" in result
        assert "details" in result
        assert "checks" in result
        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0

    def test_all_pass_score_is_1(self, tmp_path):
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text(yaml.dump(GOOD_SIMPLE_SCHEMA))
        result = run_checks(["schema-version", "attr-min-length", "no-deprecated-string"], schema_file)
        assert result["score"] == 1.0

    def test_all_fail_score_is_0(self, tmp_path):
        # Use checks that definitely fail on a nearly-empty schema:
        # - schema-version fails (version 0.0)
        # - dropdown-for-status fails (no status attr)
        # - attr-min-length fails (no nodes or generics found — guard clause)
        bad_schema = {"version": "0.0", "nodes": [], "generics": []}
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text(yaml.dump(bad_schema))
        result = run_checks(["schema-version", "dropdown-for-status", "attr-min-length"], schema_file)
        assert result["score"] == 0.0

    def test_check_entries_have_required_keys(self, tmp_path):
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text(yaml.dump(GOOD_SIMPLE_SCHEMA))
        result = run_checks(["schema-version"], schema_file)
        assert len(result["checks"]) == 1
        entry = result["checks"][0]
        assert "name" in entry
        assert "passed" in entry
        assert "message" in entry

    def test_partial_score(self, tmp_path):
        # schema-version passes, dropdown-for-status fails (no status attr)
        schema = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "display_label": "{{ name__value }}",
                    "human_friendly_id": ["name__value"],
                    "attributes": [{"name": "name", "kind": "Text"}],
                    "relationships": [],
                }
            ],
            "generics": [],
        }
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text(yaml.dump(schema))
        result = run_checks(["schema-version", "dropdown-for-status"], schema_file)
        assert result["score"] == pytest.approx(0.5)

    def test_missing_file_all_fail(self, tmp_path):
        # When the file is missing, schema == {}.
        # Checks that require data present in the schema will fail:
        # - schema-version: version is None, not "1.0"
        # - dropdown-for-status: no status attribute found
        # - display-label-singular: no display_label found
        result = run_checks(
            ["schema-version", "dropdown-for-status", "display-label-singular"],
            tmp_path / "missing.yml",
        )
        assert result["score"] == 0.0
        for entry in result["checks"]:
            assert entry["passed"] is False

    def test_unknown_check_name_raises(self, tmp_path):
        schema_file = tmp_path / "schema.yml"
        schema_file.write_text(yaml.dump(GOOD_SIMPLE_SCHEMA))
        with pytest.raises(KeyError):
            run_checks(["nonexistent-check"], schema_file)
