"""Tests for graders/managing-menus/lib.py.

Covers >= 8 check functions against both good and bad menu YAML.
"""

import importlib.util
import re
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Load the module directly — the hyphenated directory is not a valid Python
# package name, so we use importlib.util to load lib.py by file path.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "managing-menus" / "lib.py"
_spec = importlib.util.spec_from_file_location("managing_menus_graders_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CHECKS = _mod.CHECKS
_menu_items = _mod._menu_items
_all_menu_leaves = _mod._all_menu_leaves
_all_menu_items_recursive = _mod._all_menu_items_recursive
check_apiversion_and_kind = _mod.check_apiversion_and_kind
check_spec_data_structure = _mod.check_spec_data_structure
check_name_and_namespace = _mod.check_name_and_namespace
check_kind_for_schema_links = _mod.check_kind_for_schema_links
check_mdi_icons = _mod.check_mdi_icons
check_labels_present = _mod.check_labels_present
check_group_headers_no_kind = _mod.check_group_headers_no_kind
check_children_data_wrapper = _mod.check_children_data_wrapper
check_leaf_items_have_kind = _mod.check_leaf_items_have_kind
check_correct_grouping = _mod.check_correct_grouping
check_all_nodes_present = _mod.check_all_nodes_present
check_contextual_icons = _mod.check_contextual_icons
check_generic_kind_link = _mod.check_generic_kind_link
check_location_children = _mod.check_location_children
check_separate_devices_section = _mod.check_separate_devices_section
check_include_in_menu_false = _mod.check_include_in_menu_false
check_infrahub_yml_registration = _mod.check_infrahub_yml_registration
check_schema_comment = _mod.check_schema_comment
check_no_builtin_section_recreated = _mod.check_no_builtin_section_recreated
check_parent_attaches_to_builtin = _mod.check_parent_attaches_to_builtin
BUILTIN_MENU_SECTIONS = _mod.BUILTIN_MENU_SECTIONS
OBJECT_AREA_SECTIONS = _mod.OBJECT_AREA_SECTIONS
load_output = _mod.load_output
run_checks = _mod.run_checks

_GRADERS_DIR = _REPO_ROOT / "graders" / "managing-menus"


# ---------------------------------------------------------------------------
# Minimal valid menu fixtures
# ---------------------------------------------------------------------------

GOOD_FLAT_MENU = {
    "apiVersion": "infrahub.app/v1",
    "kind": "Menu",
    "spec": {
        "data": [
            {
                "name": "Server",
                "namespace": "Dcim",
                "label": "Servers",
                "icon": "mdi:server",
                "kind": "DcimServer",
            },
            {
                "name": "Switch",
                "namespace": "Dcim",
                "label": "Switches",
                "icon": "mdi:switch",
                "kind": "DcimSwitch",
            },
        ]
    },
}

GOOD_HIERARCHICAL_MENU = {
    "apiVersion": "infrahub.app/v1",
    "kind": "Menu",
    "spec": {
        "data": [
            {
                "name": "Infrastructure",
                "namespace": "Menu",
                "label": "Infrastructure",
                "icon": "mdi:server-network",
                "children": {
                    "data": [
                        {
                            "name": "Server",
                            "namespace": "Dcim",
                            "label": "Servers",
                            "icon": "mdi:server",
                            "kind": "DcimServer",
                        },
                        {
                            "name": "Switch",
                            "namespace": "Dcim",
                            "label": "Switches",
                            "icon": "mdi:switch",
                            "kind": "DcimSwitch",
                        },
                        {
                            "name": "Pdu",
                            "namespace": "Dcim",
                            "label": "PDUs",
                            "icon": "mdi:power-socket",
                            "kind": "DcimPdu",
                        },
                    ]
                },
            },
            {
                "name": "Organization",
                "namespace": "Menu",
                "label": "Organization",
                "icon": "mdi:domain",
                "children": {
                    "data": [
                        {
                            "name": "Manufacturer",
                            "namespace": "Organization",
                            "label": "Manufacturers",
                            "icon": "mdi:factory",
                            "kind": "OrganizationManufacturer",
                        },
                        {
                            "name": "Provider",
                            "namespace": "Organization",
                            "label": "Providers",
                            "icon": "mdi:cloud",
                            "kind": "OrganizationProvider",
                        },
                    ]
                },
            },
        ]
    },
}

GOOD_GENERIC_MENU = {
    "apiVersion": "infrahub.app/v1",
    "kind": "Menu",
    "spec": {
        "data": [
            {
                "name": "Locations",
                "namespace": "Menu",
                "label": "Locations",
                "icon": "mdi:map-marker",
                "kind": "LocationGeneric",
                "children": {
                    "data": [
                        {
                            "name": "Region",
                            "namespace": "Location",
                            "label": "Regions",
                            "icon": "mdi:earth",
                            "kind": "LocationRegion",
                        },
                        {
                            "name": "Site",
                            "namespace": "Location",
                            "label": "Sites",
                            "icon": "mdi:office-building",
                            "kind": "LocationSite",
                        },
                        {
                            "name": "Room",
                            "namespace": "Location",
                            "label": "Rooms",
                            "icon": "mdi:door",
                            "kind": "LocationRoom",
                        },
                        {
                            "name": "Rack",
                            "namespace": "Location",
                            "label": "Racks",
                            "icon": "mdi:server-network",
                            "kind": "LocationRack",
                        },
                    ]
                },
            },
            {
                "name": "Devices",
                "namespace": "Menu",
                "label": "Devices",
                "icon": "mdi:devices",
                "children": {
                    "data": [
                        {
                            "name": "Device",
                            "namespace": "Dcim",
                            "label": "Devices",
                            "icon": "mdi:server",
                            "kind": "DcimDevice",
                        },
                    ]
                },
            },
        ]
    },
}

GOOD_GENERIC_MENU_RAW = yaml.dump(GOOD_GENERIC_MENU) + "\n# include_in_menu: false\n# .infrahub.yml\n# $schema: ...\n"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_menu_items_returns_top_level(self):
        items = _menu_items(GOOD_FLAT_MENU)
        assert len(items) == 2

    def test_menu_items_empty_on_bad_doc(self):
        assert _menu_items({}) == []

    def test_all_menu_leaves_flat(self):
        leaves = _all_menu_leaves(GOOD_FLAT_MENU)
        assert len(leaves) == 2
        assert all(item.get("kind") for item in leaves)

    def test_all_menu_leaves_hierarchical(self):
        leaves = _all_menu_leaves(GOOD_HIERARCHICAL_MENU)
        # All 5 children are leaf items with kind
        assert len(leaves) == 5

    def test_all_menu_items_recursive_flat(self):
        items = _all_menu_items_recursive(GOOD_FLAT_MENU)
        assert len(items) == 2

    def test_all_menu_items_recursive_hierarchical(self):
        items = _all_menu_items_recursive(GOOD_HIERARCHICAL_MENU)
        # 2 group headers + 5 children = 7
        assert len(items) == 7


# ---------------------------------------------------------------------------
# check_apiversion_and_kind
# ---------------------------------------------------------------------------


class TestCheckApiversionAndKind:
    def test_good(self):
        ok, msg = check_apiversion_and_kind(GOOD_FLAT_MENU)
        assert ok is True
        assert "infrahub.app/v1" in msg

    def test_bad_wrong_api_version(self):
        doc = {"apiVersion": "v1", "kind": "Menu"}
        ok, msg = check_apiversion_and_kind(doc)
        assert ok is False

    def test_bad_wrong_kind(self):
        doc = {"apiVersion": "infrahub.app/v1", "kind": "Schema"}
        ok, msg = check_apiversion_and_kind(doc)
        assert ok is False

    def test_bad_empty(self):
        ok, msg = check_apiversion_and_kind({})
        assert ok is False


# ---------------------------------------------------------------------------
# check_spec_data_structure
# ---------------------------------------------------------------------------


class TestCheckSpecDataStructure:
    def test_good(self):
        ok, msg = check_spec_data_structure(GOOD_FLAT_MENU)
        assert ok is True
        assert "2" in msg

    def test_bad_no_spec(self):
        ok, msg = check_spec_data_structure({})
        assert ok is False
        assert "spec" in msg.lower()

    def test_bad_spec_not_dict(self):
        ok, msg = check_spec_data_structure({"spec": "string"})
        assert ok is False

    def test_bad_data_not_list(self):
        ok, msg = check_spec_data_structure({"spec": {"data": {}}})
        assert ok is False
        assert "list" in msg

    def test_bad_empty_data(self):
        ok, msg = check_spec_data_structure({"spec": {"data": []}})
        assert ok is False
        assert "empty" in msg


# ---------------------------------------------------------------------------
# check_name_and_namespace
# ---------------------------------------------------------------------------


class TestCheckNameAndNamespace:
    def test_good(self):
        ok, msg = check_name_and_namespace(GOOD_FLAT_MENU)
        assert ok is True

    def test_bad_empty_doc(self):
        ok, msg = check_name_and_namespace({})
        assert ok is False
        assert "No menu items found" in msg

    def test_bad_missing_name(self):
        doc = {
            "apiVersion": "infrahub.app/v1",
            "kind": "Menu",
            "spec": {
                "data": [
                    {"namespace": "Dcim", "label": "Servers", "icon": "mdi:server", "kind": "DcimServer"}
                ]
            },
        }
        ok, msg = check_name_and_namespace(doc)
        assert ok is False
        assert "name" in msg

    def test_bad_missing_namespace(self):
        doc = {
            "apiVersion": "infrahub.app/v1",
            "kind": "Menu",
            "spec": {
                "data": [
                    {"name": "Server", "label": "Servers", "icon": "mdi:server", "kind": "DcimServer"}
                ]
            },
        }
        ok, msg = check_name_and_namespace(doc)
        assert ok is False
        assert "namespace" in msg


# ---------------------------------------------------------------------------
# check_kind_for_schema_links
# ---------------------------------------------------------------------------


class TestCheckKindForSchemaLinks:
    def test_good(self):
        ok, msg = check_kind_for_schema_links(GOOD_FLAT_MENU)
        assert ok is True

    def test_bad_uses_path(self):
        doc = {
            "spec": {
                "data": [
                    {"name": "Server", "namespace": "Dcim", "label": "Servers", "path": "/servers"}
                ]
            }
        }
        ok, msg = check_kind_for_schema_links(doc)
        assert ok is False
        assert "path" in msg.lower() or "kind" in msg.lower()

    def test_bad_no_leaves(self):
        ok, msg = check_kind_for_schema_links({"spec": {"data": []}})
        assert ok is False


# ---------------------------------------------------------------------------
# check_mdi_icons
# ---------------------------------------------------------------------------


class TestCheckMdiIcons:
    def test_good(self):
        ok, msg = check_mdi_icons(GOOD_FLAT_MENU)
        assert ok is True

    def test_bad_empty_doc(self):
        ok, msg = check_mdi_icons({})
        assert ok is False
        assert "No menu items found" in msg

    def test_bad_missing_mdi_prefix(self):
        doc = {
            "spec": {
                "data": [
                    {
                        "name": "Server",
                        "namespace": "Dcim",
                        "label": "Servers",
                        "icon": "server",  # no mdi: prefix
                        "kind": "DcimServer",
                    }
                ]
            }
        }
        ok, msg = check_mdi_icons(doc)
        assert ok is False
        assert "mdi:" in msg

    def test_bad_no_icon(self):
        doc = {
            "spec": {
                "data": [
                    {"name": "Server", "namespace": "Dcim", "label": "Servers", "kind": "DcimServer"}
                ]
            }
        }
        ok, msg = check_mdi_icons(doc)
        assert ok is False
        assert "no icon" in msg


# ---------------------------------------------------------------------------
# check_labels_present
# ---------------------------------------------------------------------------


class TestCheckLabelsPresent:
    def test_good(self):
        ok, msg = check_labels_present(GOOD_FLAT_MENU)
        assert ok is True

    def test_bad_empty_doc(self):
        ok, msg = check_labels_present({})
        assert ok is False
        assert "No menu items found" in msg

    def test_bad_missing_label(self):
        doc = {
            "spec": {
                "data": [
                    {"name": "Server", "namespace": "Dcim", "icon": "mdi:server", "kind": "DcimServer"}
                ]
            }
        }
        ok, msg = check_labels_present(doc)
        assert ok is False
        assert "Server" in msg


# ---------------------------------------------------------------------------
# check_group_headers_no_kind
# ---------------------------------------------------------------------------


class TestCheckGroupHeadersNoKind:
    def test_good(self):
        ok, msg = check_group_headers_no_kind(GOOD_HIERARCHICAL_MENU)
        assert ok is True
        assert "2" in msg

    def test_bad_no_group_headers(self):
        # Flat menu — no children at top level
        ok, msg = check_group_headers_no_kind(GOOD_FLAT_MENU)
        assert ok is False

    def test_bad_group_with_kind(self):
        doc = {
            "spec": {
                "data": [
                    {
                        "name": "Infrastructure",
                        "namespace": "Menu",
                        "label": "Infrastructure",
                        "icon": "mdi:server-network",
                        "kind": "SomeKind",  # should not have kind
                        "children": {"data": []},
                    }
                ]
            }
        }
        ok, msg = check_group_headers_no_kind(doc)
        assert ok is False


# ---------------------------------------------------------------------------
# check_children_data_wrapper
# ---------------------------------------------------------------------------


class TestCheckChildrenDataWrapper:
    def test_good(self):
        ok, msg = check_children_data_wrapper(GOOD_HIERARCHICAL_MENU)
        assert ok is True

    def test_bad_empty_doc(self):
        ok, msg = check_children_data_wrapper({})
        assert ok is False
        assert "No menu items found" in msg

    def test_bad_children_as_list(self):
        doc = {
            "spec": {
                "data": [
                    {
                        "name": "Infrastructure",
                        "namespace": "Menu",
                        "label": "Infrastructure",
                        "icon": "mdi:server-network",
                        "children": [  # list, not dict with data key
                            {"name": "Server", "namespace": "Dcim", "label": "Servers",
                             "icon": "mdi:server", "kind": "DcimServer"}
                        ],
                    }
                ]
            }
        }
        ok, msg = check_children_data_wrapper(doc)
        assert ok is False
        assert "list" in msg.lower() or "data" in msg.lower()

    def test_good_no_children(self):
        # Items with no children should pass trivially
        ok, msg = check_children_data_wrapper(GOOD_FLAT_MENU)
        assert ok is True


# ---------------------------------------------------------------------------
# check_leaf_items_have_kind
# ---------------------------------------------------------------------------


class TestCheckLeafItemsHaveKind:
    def test_good(self):
        ok, msg = check_leaf_items_have_kind(GOOD_FLAT_MENU)
        assert ok is True

    def test_bad_no_kind(self):
        doc = {
            "spec": {
                "data": [
                    {"name": "Server", "namespace": "Dcim", "label": "Servers", "icon": "mdi:server"}
                ]
            }
        }
        ok, msg = check_leaf_items_have_kind(doc)
        assert ok is False


# ---------------------------------------------------------------------------
# check_correct_grouping
# ---------------------------------------------------------------------------


class TestCheckCorrectGrouping:
    def test_good(self):
        ok, msg = check_correct_grouping(GOOD_HIERARCHICAL_MENU)
        assert ok is True

    def test_bad_wrong_grouping(self):
        # Put servers under organization instead of infrastructure
        doc = {
            "spec": {
                "data": [
                    {
                        "name": "Organization",
                        "namespace": "Menu",
                        "label": "Organization",
                        "icon": "mdi:domain",
                        "children": {
                            "data": [
                                {"name": "Server", "namespace": "Dcim", "label": "Servers",
                                 "icon": "mdi:server", "kind": "DcimServer"},
                            ]
                        },
                    },
                ]
            }
        }
        ok, msg = check_correct_grouping(doc)
        assert ok is False


# ---------------------------------------------------------------------------
# check_all_nodes_present
# ---------------------------------------------------------------------------


class TestCheckAllNodesPresent:
    def test_good(self):
        ok, msg = check_all_nodes_present(GOOD_HIERARCHICAL_MENU)
        assert ok is True
        assert "5" in msg

    def test_bad_missing_nodes(self):
        ok, msg = check_all_nodes_present(GOOD_FLAT_MENU)
        assert ok is False
        assert "Missing" in msg


# ---------------------------------------------------------------------------
# check_contextual_icons
# ---------------------------------------------------------------------------


class TestCheckContextualIcons:
    def test_good(self):
        ok, msg = check_contextual_icons(GOOD_HIERARCHICAL_MENU)
        assert ok is True

    def test_bad_non_mdi_icon(self):
        doc = {
            "spec": {
                "data": [
                    {"name": "Server", "namespace": "Dcim", "label": "Servers",
                     "icon": "fa-server", "kind": "DcimServer"}
                ]
            }
        }
        ok, msg = check_contextual_icons(doc)
        assert ok is False

    def test_bad_no_items(self):
        ok, msg = check_contextual_icons({"spec": {"data": []}})
        assert ok is False


# ---------------------------------------------------------------------------
# check_generic_kind_link
# ---------------------------------------------------------------------------


class TestCheckGenericKindLink:
    def test_good(self):
        ok, msg = check_generic_kind_link(GOOD_GENERIC_MENU)
        assert ok is True
        assert "LocationGeneric" in msg

    def test_bad_no_generic(self):
        ok, msg = check_generic_kind_link(GOOD_FLAT_MENU)
        assert ok is False


# ---------------------------------------------------------------------------
# check_location_children
# ---------------------------------------------------------------------------


class TestCheckLocationChildren:
    def test_good(self):
        ok, msg = check_location_children(GOOD_GENERIC_MENU)
        assert ok is True

    def test_bad_missing_location_types(self):
        ok, msg = check_location_children(GOOD_FLAT_MENU)
        assert ok is False
        assert "Missing" in msg


# ---------------------------------------------------------------------------
# check_separate_devices_section
# ---------------------------------------------------------------------------


class TestCheckSeparateDevicesSection:
    def test_good(self):
        ok, msg = check_separate_devices_section(GOOD_GENERIC_MENU)
        assert ok is True

    def test_bad_no_devices_section(self):
        ok, msg = check_separate_devices_section(GOOD_FLAT_MENU)
        assert ok is False


# ---------------------------------------------------------------------------
# check_include_in_menu_false
# ---------------------------------------------------------------------------


class TestCheckIncludeInMenuFalse:
    def test_good_raw_text(self):
        ok, msg = check_include_in_menu_false({}, raw_text="include_in_menu: false")
        assert ok is True

    def test_bad_no_mention(self):
        ok, msg = check_include_in_menu_false({}, raw_text="nothing relevant here")
        assert ok is False


# ---------------------------------------------------------------------------
# check_infrahub_yml_registration
# ---------------------------------------------------------------------------


class TestCheckInfrahubYmlRegistration:
    def test_good_raw_text(self):
        ok, msg = check_infrahub_yml_registration({}, raw_text="register in .infrahub.yml")
        assert ok is True

    def test_bad_no_mention(self):
        ok, msg = check_infrahub_yml_registration({}, raw_text="nothing here")
        assert ok is False


# ---------------------------------------------------------------------------
# check_schema_comment
# ---------------------------------------------------------------------------


class TestCheckSchemaComment:
    def test_good_schema_comment(self):
        ok, msg = check_schema_comment({}, raw_text="# $schema: https://...")
        assert ok is True

    def test_good_yaml_language_server(self):
        ok, msg = check_schema_comment({}, raw_text="# yaml-language-server: $schema=...")
        assert ok is True

    def test_bad_no_comment(self):
        ok, msg = check_schema_comment({}, raw_text="apiVersion: infrahub.app/v1")
        assert ok is False


# ---------------------------------------------------------------------------
# load_output
# ---------------------------------------------------------------------------


class TestLoadOutput:
    def test_loads_yaml_file(self, tmp_path):
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_FLAT_MENU))
        doc, raw = load_output(menu_file)
        assert doc["apiVersion"] == "infrahub.app/v1"
        assert "apiVersion" in raw

    def test_missing_file_returns_empty(self, tmp_path):
        doc, raw = load_output(tmp_path / "nonexistent.yml")
        assert doc == {}
        assert raw == ""


# ---------------------------------------------------------------------------
# CHECKS dict
# ---------------------------------------------------------------------------


class TestChecksDict:
    def test_all_expected_keys_present(self):
        expected = {
            "apiversion-and-kind",
            "spec-data-structure",
            "name-and-namespace",
            "kind-for-schema-links",
            "mdi-icons",
            "labels-present",
            "group-headers-no-kind",
            "children-data-wrapper",
            "leaf-items-have-kind",
            "correct-grouping",
            "all-nodes-present",
            "contextual-icons",
            "generic-kind-link",
            "location-children",
            "separate-devices-section",
            "include-in-menu-false",
            "infrahub-yml-registration",
            "schema-comment",
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
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_FLAT_MENU))
        result = run_checks(["apiversion-and-kind", "spec-data-structure"], menu_file)
        assert "score" in result
        assert "details" in result
        assert "checks" in result
        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0

    def test_all_pass_score_is_1(self, tmp_path):
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_FLAT_MENU))
        result = run_checks(
            ["apiversion-and-kind", "spec-data-structure", "labels-present"],
            menu_file,
        )
        assert result["score"] == 1.0

    def test_all_fail_score_is_0(self, tmp_path):
        bad_doc = {"foo": "bar"}
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(bad_doc))
        result = run_checks(
            ["apiversion-and-kind", "spec-data-structure"],
            menu_file,
        )
        assert result["score"] == 0.0

    def test_check_entries_have_required_keys(self, tmp_path):
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_FLAT_MENU))
        result = run_checks(["apiversion-and-kind"], menu_file)
        assert len(result["checks"]) == 1
        entry = result["checks"][0]
        assert "name" in entry
        assert "passed" in entry
        assert "message" in entry

    def test_missing_file_all_fail(self, tmp_path):
        result = run_checks(
            ["apiversion-and-kind", "spec-data-structure"],
            tmp_path / "missing.yml",
        )
        assert result["score"] == 0.0
        for entry in result["checks"]:
            assert entry["passed"] is False

    def test_unknown_check_name_raises(self, tmp_path):
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_FLAT_MENU))
        with pytest.raises(KeyError):
            run_checks(["nonexistent-check"], menu_file)


# ---------------------------------------------------------------------------
# Grader script integration tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Built-in menu section collisions (issue #24)
#
# The four fixtures below are the compliant / compliant-variant / violating /
# violating-near-miss set that rule-equals-test.md asks for, committed here so
# they run under `uv run invoke test` rather than only inside a skillgrade run.
# ---------------------------------------------------------------------------


def _menu(*items: dict) -> dict:
    """Wrap menu items in the apiVersion/kind/spec envelope."""
    return {"apiVersion": "infrahub.app/v1", "kind": "Menu", "spec": {"data": list(items)}}


def _children(*items: dict) -> dict:
    return {"data": list(items)}


# Compliant: each IPAM-domain item attaches to the shipped section directly.
BUILTIN_PASS = _menu(
    {
        "namespace": "Ipam",
        "name": "Vlans",
        "label": "VLANs",
        "kind": "IpamVlan",
        "icon": "mdi:lan",
        "parent": ["Builtin", "IPAM"],
    },
    {
        "namespace": "Ipam",
        "name": "Vrfs",
        "label": "VRFs",
        "kind": "IpamVrf",
        "icon": "mdi:router-network",
        "parent": ["Builtin", "IPAM"],
    },
    {
        "namespace": "Dcim",
        "name": "NetworkDevices",
        "label": "Network Devices",
        "icon": "mdi:server-network",
        "children": _children(
            {"namespace": "Dcim", "name": "Device", "label": "Devices", "kind": "DcimDevice"},
        ),
    },
)

# Compliant variant: one parented group carries both, fields in another order.
BUILTIN_PASS_VARIANT = _menu(
    {
        "parent": ["Builtin", "IPAM"],
        "namespace": "Ipam",
        "name": "Addressing",
        "icon": "mdi:ip-network-outline",
        "label": "Addressing",
        "children": _children(
            {"namespace": "Ipam", "name": "Vrf", "kind": "IpamVrf", "label": "VRFs"},
            {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
        ),
    },
    {"namespace": "Organization", "name": "Customer", "label": "Customers", "kind": "OrganizationCustomer"},
)

# Violating: recreates BuiltinIPAM outright.
BUILTIN_FAIL = _menu(
    {
        "namespace": "Builtin",
        "name": "IPAM",
        "label": "IPAM",
        "icon": "mdi:ip-network",
        "children": _children(
            {"namespace": "Ipam", "name": "Vlan", "label": "VLANs", "kind": "IpamVlan"},
            {"namespace": "Ipam", "name": "Vrf", "label": "VRFs", "kind": "IpamVrf"},
        ),
    },
)

# Violating near miss: a different identifier, but the sidebar still shows a
# second "IPAM" heading, and the parent values point at the custom group rather
# than the shipped section.
BUILTIN_FAIL_NEARMISS = _menu(
    {
        "namespace": "Ipam",
        "name": "Management",
        "label": "IPAM",
        "icon": "mdi:ip-network",
        "children": _children(
            {
                "namespace": "Ipam",
                "name": "Vlan",
                "label": "VLANs",
                "kind": "IpamVlan",
                "parent": "IpamManagement",
            },
        ),
    },
)


class TestCheckNoBuiltinSectionRecreated:
    def test_compliant_passes(self):
        ok, msg = check_no_builtin_section_recreated(BUILTIN_PASS)
        assert ok, msg

    def test_compliant_variant_passes(self):
        ok, msg = check_no_builtin_section_recreated(BUILTIN_PASS_VARIANT)
        assert ok, msg

    def test_recreated_identifier_fails(self):
        ok, msg = check_no_builtin_section_recreated(BUILTIN_FAIL)
        assert not ok
        assert "BuiltinIPAM" in msg

    def test_near_miss_label_collision_fails(self):
        """A fresh identifier does not help: the sidebar still shows two IPAM headings."""
        ok, msg = check_no_builtin_section_recreated(BUILTIN_FAIL_NEARMISS)
        assert not ok
        assert "IPAM" in msg

    def test_empty_doc_fails(self):
        ok, msg = check_no_builtin_section_recreated({})
        assert not ok
        assert "No menu items" in msg

    @pytest.mark.parametrize("label", ["Other", "Actions", "Object Management"])
    def test_generic_label_matching_a_shipped_section_is_flagged(self, label):
        """Deliberate: these read as duplicates in the sidebar whatever the namespace.

        "Other" and "Actions" are plausible names for an unrelated custom group,
        but Infrahub renders its own sections under those exact labels, so a
        second top-level item with the same label is the defect from #24. The
        rule's answer is to relabel the group.
        """
        doc = _menu({"namespace": "Custom", "name": "Group", "label": label, "children": _children()})
        ok, _ = check_no_builtin_section_recreated(doc)
        assert not ok

    @pytest.mark.parametrize(
        ("name", "label"),
        [
            ("Actions", "Device Actions"),
            ("ObjectManagement", "Fleet Inventory"),
            ("IPAM", "Customer Addressing"),
        ],
    )
    def test_distinct_label_over_a_colliding_name_passes(self, name, label):
        """The sidebar renders `label`, so a colliding `name` behind it is invisible.

        Regression test for PR #153 review: `name` was checked independently of
        `label`, so a "Device Actions" group whose name happened to be "Actions"
        was reported as a duplicate of the shipped Actions section. Its
        identifier is DcimActions and its heading is "Device Actions", so it
        collides with nothing.
        """
        doc = _menu({"namespace": "Dcim", "name": name, "label": label, "children": _children()})
        ok, msg = check_no_builtin_section_recreated(doc)
        assert ok, msg

    @pytest.mark.parametrize(
        "section", ["Branches", "ObjectManagement", "Actions", "Admin", "Integration"]
    )
    def test_object_content_under_a_platform_section_is_flagged(self, section):
        """Attaching user nodes to a platform section buries them in Infrahub's UI.

        Regression test for PR #153 review: a "Network Devices" group carrying
        DcimDevice on `parent: [Builtin, Branches]` passed both checks, so the
        rule's object/platform split had nothing measuring it.
        """
        doc = _menu(
            {
                "namespace": "Dcim",
                "name": "NetworkDevices",
                "label": "Network Devices",
                "parent": ["Builtin", section],
                "children": _children(
                    {"namespace": "Dcim", "name": "Device", "kind": "DcimDevice", "label": "Devices"},
                ),
            }
        )
        ok, msg = check_no_builtin_section_recreated(doc)
        assert not ok
        assert f"Builtin{section}" in msg

    @pytest.mark.parametrize("section", ["Other", "IPAM"])
    def test_object_content_under_an_object_section_passes(self, section):
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Addressing",
                "label": "Addressing",
                "parent": ["Builtin", section],
                "children": _children(
                    {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
                ),
            }
        )
        ok, msg = check_no_builtin_section_recreated(doc)
        assert ok, msg

    def test_parenting_to_your_own_group_is_ordinary_nesting(self):
        """`parent` takes any CoreMenu HFID, not only a built-in one.

        Regression test for PR #153 review: the platform-section guard treated
        every resolvable parent outside the object area as a platform section,
        so a DcimDevice item on `parent: [Dcim, NetworkDevices]` was scored as
        a violation, with a message calling the user's own group a platform
        section. The same menu written with children.data alone passed, and no
        rule forbids the parent form.
        """
        doc = _menu(
            {
                "namespace": "Dcim",
                "name": "NetworkDevices",
                "label": "Network Devices",
                "children": _children(
                    {
                        "namespace": "Dcim",
                        "name": "Device",
                        "kind": "DcimDevice",
                        "label": "Devices",
                        "parent": ["Dcim", "NetworkDevices"],
                    },
                ),
            }
        )
        ok, msg = check_no_builtin_section_recreated(doc)
        assert ok, msg

    def test_misspelled_builtin_is_not_called_a_platform_section(self):
        """`[Builtin, Ipam]` is a lookup failure, which the other check reports."""
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Addressing",
                "label": "Addressing",
                "parent": ["Builtin", "Ipam"],
                "children": _children(
                    {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
                ),
            }
        )
        ok, msg = check_no_builtin_section_recreated(doc)
        assert ok, msg

    def test_headers_only_under_a_platform_section_are_left_alone(self):
        """No `kind` anywhere in the subtree means no object content to misplace."""
        doc = _menu(
            {
                "namespace": "Custom",
                "name": "Notes",
                "label": "Notes",
                "parent": ["Builtin", "Admin"],
                "children": _children(),
            }
        )
        ok, msg = check_no_builtin_section_recreated(doc)
        assert ok, msg

    def test_colliding_name_without_label_is_flagged(self):
        """With no label, `name` is what the sidebar falls back to."""
        doc = _menu({"namespace": "Dcim", "name": "IPAM", "children": _children()})
        ok, msg = check_no_builtin_section_recreated(doc)
        assert not ok
        assert "IPAM" in msg

    def test_parented_item_may_reuse_a_shipped_label(self):
        """An item with a parent is not top level, so it cannot collide."""
        doc = _menu(
            {
                "namespace": "Custom",
                "name": "Group",
                "label": "Actions",
                "parent": ["Builtin", "IPAM"],
                "children": _children(),
            }
        )
        ok, msg = check_no_builtin_section_recreated(doc)
        assert ok, msg


class TestCheckParentAttachesToBuiltin:
    def test_compliant_passes(self):
        ok, msg = check_parent_attaches_to_builtin(BUILTIN_PASS)
        assert ok, msg

    def test_compliant_variant_passes(self):
        ok, msg = check_parent_attaches_to_builtin(BUILTIN_PASS_VARIANT)
        assert ok, msg

    def test_no_parent_fails(self):
        ok, msg = check_parent_attaches_to_builtin(BUILTIN_FAIL)
        assert not ok
        assert "no item declares a parent" in msg

    def test_near_miss_parent_to_custom_item_fails(self):
        ok, msg = check_parent_attaches_to_builtin(BUILTIN_FAIL_NEARMISS)
        assert not ok
        assert "IpamManagement" in msg

    def test_wrong_builtin_section_fails(self):
        """Attaching under any shipped section is not the same as reaching IPAM.

        Regression test for PR #153 review: membership in the built-in set let
        `parent: BuiltinActions` score a pass even though the VLAN and VRF
        entries never landed under IPAM.
        """
        doc = _menu(
            {
                "parent": ["Builtin", "Actions"],
                "namespace": "Ipam",
                "name": "Addressing",
                "label": "Addressing",
                "children": _children(
                    {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
                    {"namespace": "Ipam", "name": "Vrf", "kind": "IpamVrf", "label": "VRFs"},
                ),
            }
        )
        ok, msg = check_parent_attaches_to_builtin(doc)
        assert not ok
        assert "BuiltinActions" in msg

    def test_partial_coverage_fails(self):
        """Only one of the two IPAM-domain kinds reaches the shipped section."""
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Vlans",
                "kind": "IpamVlan",
                "label": "VLANs",
                "parent": ["Builtin", "IPAM"],
            },
            {"namespace": "Ipam", "name": "Vrfs", "kind": "IpamVrf", "label": "VRFs"},
        )
        ok, msg = check_parent_attaches_to_builtin(doc)
        assert not ok
        assert "ipamvrf" in msg

    def test_hfid_pair_form_passes(self):
        """`parent: [Builtin, IPAM]` matches CoreMenu's two-part human-friendly ID."""
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Addressing",
                "label": "Addressing",
                "parent": ["Builtin", "IPAM"],
                "children": _children(
                    {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
                    {"namespace": "Ipam", "name": "Vrf", "kind": "IpamVrf", "label": "VRFs"},
                ),
            }
        )
        ok, msg = check_parent_attaches_to_builtin(doc)
        assert ok, msg

    def test_hfid_pair_form_for_wrong_section_fails(self):
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Addressing",
                "label": "Addressing",
                "parent": ["Builtin", "Actions"],
                "children": _children(
                    {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
                    {"namespace": "Ipam", "name": "Vrf", "kind": "IpamVrf", "label": "VRFs"},
                ),
            }
        )
        ok, msg = check_parent_attaches_to_builtin(doc)
        assert not ok
        assert "BuiltinActions" in msg

    @pytest.mark.parametrize(
        "parent",
        ["BuiltinIPAM", ["BuiltinIPAM"], ["Built", "in", "IPAM"], ["Builtin"]],
    )
    def test_only_the_two_element_list_resolves(self, parent):
        """Anything but a two-element HFID fails to load, so it must not score.

        Measured on infrahub-sdk 1.23.2: `normalize_hfid_reference` turns the
        concatenated string into a one-element HFID and passes lists through at
        whatever length they arrive. CoreMenu's HFID is two components and the
        backend compares lengths before querying, so one- and three-element
        forms raise NodeNotFoundError.

        Earlier in PR #153 this check folded the string form in as an
        equivalent spelling, which meant it scored a file that cannot load.
        """
        kinds = _children(
            {"namespace": "Ipam", "name": "Vlan", "kind": "IpamVlan", "label": "VLANs"},
            {"namespace": "Ipam", "name": "Vrf", "kind": "IpamVrf", "label": "VRFs"},
        )
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Addressing",
                "label": "Addressing",
                "parent": parent,
                "children": kinds,
            }
        )
        ok, msg = check_parent_attaches_to_builtin(doc)
        assert not ok
        assert "two-element" in msg or "no item declares a parent" in msg

    def test_parent_match_is_exact(self):
        """`BuiltinIpam` resolves to nothing in Infrahub, so it must not pass here."""
        doc = _menu(
            {
                "namespace": "Ipam",
                "name": "Vlans",
                "kind": "IpamVlan",
                "label": "VLANs",
                "parent": ["Builtin", "Ipam"],
            },
            {
                "namespace": "Ipam",
                "name": "Vrfs",
                "kind": "IpamVrf",
                "label": "VRFs",
                "parent": ["Builtin", "Ipam"],
            },
        )
        ok, _ = check_parent_attaches_to_builtin(doc)
        assert not ok

    def test_empty_doc_fails(self):
        ok, msg = check_parent_attaches_to_builtin({})
        assert not ok
        assert "No menu items" in msg


class TestBuiltinMenuSectionsRegistry:
    def test_registry_is_keyed_by_identifier(self):
        """Keys are <namespace><name>, the value `parent:` takes in a menu file."""
        assert "BuiltinIPAM" in BUILTIN_MENU_SECTIONS
        assert all(k.startswith("Builtin") for k in BUILTIN_MENU_SECTIONS)

    def test_both_new_checks_are_registered(self):
        assert CHECKS["no-builtin-section-recreated"] is check_no_builtin_section_recreated
        assert CHECKS["parent-attaches-to-builtin"] is check_parent_attaches_to_builtin

    def test_rule_tables_match_the_constant(self):
        """The rule and the grader hold the same list, so pin them to each other.

        Both are copies of `default_menu` in Infrahub's backend. Nothing failed
        when they drifted, which is the objection raised on PR #153; this is the
        failure. Update both together when Infrahub adds or renames a section.
        """
        rule = (
            _REPO_ROOT / "skills" / "infrahub-managing-menus" / "rules" / "hierarchy-nesting.md"
        ).read_text(encoding="utf-8")

        documented = {
            m.group(1): m.group(2).strip()
            for m in re.finditer(r"^\|\s*`(Builtin\w+)`\s*\|\s*([^|]+?)\s*\|\s*$", rule, re.MULTILINE)
        }

        assert documented, "no built-in section table found in hierarchy-nesting.md"
        assert documented == BUILTIN_MENU_SECTIONS, (
            "hierarchy-nesting.md and BUILTIN_MENU_SECTIONS disagree; "
            f"only in the rule: {sorted(set(documented) - set(BUILTIN_MENU_SECTIONS))}, "
            f"only in the grader: {sorted(set(BUILTIN_MENU_SECTIONS) - set(documented))}"
        )

    def test_object_area_sections_are_the_attach_targets(self):
        """Only Other and IPAM are section=object in Infrahub; the rest are internal.

        The rule splits its tables on this, and the prose tells the agent to
        attach only to the object ones. If Infrahub promotes another section,
        this is the test that has to be revisited alongside the rule.
        """
        rule = (
            _REPO_ROOT / "skills" / "infrahub-managing-menus" / "rules" / "hierarchy-nesting.md"
        ).read_text(encoding="utf-8")
        object_area, _, platform_area = rule.partition("Infrahub's own area")
        # Table rows only. Prose in this rule also names generics such as
        # BuiltinIPPrefix, which are schema kinds rather than menu sections.
        row = r"^\|\s*`(Builtin\w+)`\s*\|"
        object_ids = set(
            re.findall(row, object_area.split("Object area")[-1], re.MULTILINE)
        )
        platform_ids = set(re.findall(row, platform_area, re.MULTILINE))

        assert object_ids == set(OBJECT_AREA_SECTIONS), (
            "the rule's object table and OBJECT_AREA_SECTIONS disagree; "
            f"rule: {sorted(object_ids)}, grader: {sorted(OBJECT_AREA_SECTIONS)}"
        )
        assert platform_ids == set(BUILTIN_MENU_SECTIONS) - set(OBJECT_AREA_SECTIONS)
        assert not object_ids & platform_ids


class TestGraderScripts:
    """Test that each grader script outputs valid JSON when no file exists (score 0.0)."""

    def _run_script(self, script_name: str, menu_path: str) -> dict:
        script = _GRADERS_DIR / script_name
        result = subprocess.run(
            [sys.executable, str(script), menu_path],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script {script_name} failed: {result.stderr}"
        return json.loads(result.stdout)

    def test_check_flat_menu_missing_file(self, tmp_path):
        """Missing file produces valid JSON with score 0.0; all checks fail on empty doc."""
        result = self._run_script("check_flat_menu.py", str(tmp_path / "missing.yml"))
        assert "score" in result
        assert "details" in result
        assert "checks" in result
        assert result["score"] == 0.0

    def test_check_hierarchical_missing_file(self, tmp_path):
        """Missing file produces valid JSON with score 0.0; all checks fail on empty doc."""
        result = self._run_script("check_hierarchical.py", str(tmp_path / "missing.yml"))
        assert "score" in result
        assert "details" in result
        assert "checks" in result
        assert result["score"] == 0.0

    def test_check_generic_kind_missing_file(self, tmp_path):
        """Missing file produces valid JSON with score 0.0; all checks fail on empty doc."""
        result = self._run_script("check_generic_kind.py", str(tmp_path / "missing.yml"))
        assert "score" in result
        assert "details" in result
        assert "checks" in result
        assert result["score"] == 0.0

    def test_check_flat_menu_valid_input_score_1(self, tmp_path):
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_FLAT_MENU))
        result = self._run_script("check_flat_menu.py", str(menu_file))
        assert result["score"] == 1.0

    def test_check_hierarchical_valid_input_score_1(self, tmp_path):
        menu_file = tmp_path / "menu.yml"
        menu_file.write_text(yaml.dump(GOOD_HIERARCHICAL_MENU))
        result = self._run_script("check_hierarchical.py", str(menu_file))
        assert result["score"] == 1.0

    def test_check_builtin_sections_missing_file(self, tmp_path):
        """Missing file produces valid JSON with score 0.0; all checks fail on empty doc."""
        result = self._run_script("check_builtin_sections.py", str(tmp_path / "missing.yml"))
        assert "score" in result
        assert "details" in result
        assert "checks" in result
        assert result["score"] == 0.0

    def test_check_builtin_sections_four_fixtures(self, tmp_path):
        """The four fixtures score 1.0 / 1.0 / <1.0 / <1.0 end to end."""
        expectations = [
            ("pass", BUILTIN_PASS, True),
            ("pass-variant", BUILTIN_PASS_VARIANT, True),
            ("fail", BUILTIN_FAIL, False),
            ("fail-nearmiss", BUILTIN_FAIL_NEARMISS, False),
        ]
        for name, doc, should_pass in expectations:
            menu_file = tmp_path / f"{name}.yml"
            menu_file.write_text(yaml.dump(doc))
            result = self._run_script("check_builtin_sections.py", str(menu_file))
            if should_pass:
                assert result["score"] == 1.0, f"{name}: {result['details']}"
            else:
                assert result["score"] < 1.0, f"{name} scored 1.0: {result['details']}"

    def test_all_scripts_output_valid_json(self, tmp_path):
        scripts = [
            "check_flat_menu.py",
            "check_hierarchical.py",
            "check_generic_kind.py",
            "check_builtin_sections.py",
            "check_remove_synced_items.py",
        ]
        for script in scripts:
            result = self._run_script(script, str(tmp_path / "missing.yml"))
            # Must be valid JSON with required keys
            assert isinstance(result.get("score"), float)
            assert isinstance(result.get("details"), str)
            assert isinstance(result.get("checks"), list)


# ---------------------------------------------------------------------------
# Removing items from a menu already loaded with infrahubctl menu load
# ---------------------------------------------------------------------------

REMOVE_MENU_KEPT = """\
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/menu/latest.json
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Campus
      name: SitesMenu
      label: Sites
      icon: "mdi:office-building"
      children:
        data:
          - namespace: Campus
            name: BuildingMenu
            label: Buildings
            kind: CampusBuilding
            icon: "mdi:domain"
    - namespace: Campus
      name: SwitchingMenu
      label: Switching
      icon: "mdi:switch"
      children:
        data:
          - namespace: Campus
            name: SwitchMenu
            label: Switches
            kind: CampusSwitch
            icon: "mdi:switch"
"""

REMOVE_APPLY_PASS = """\
# Apply

1. Load the new file:

```bash
infrahubctl menu load menus/campus.yml
```

2. The load never deletes, so remove the dropped items:

```graphql
mutation RemoveRetiredMenuItems {
  floors: CoreMenuItemDelete(data: {hfid: ["Campus", "FloorMenu"]}) { ok }
  aps: CoreMenuItemDelete(data: {hfid: ["Campus", "AccessPointMenu"]}) { ok }
  ctrl: CoreMenuItemDelete(data: {hfid: ["Campus", "ControllerMenu"]}) { ok }
  wireless: CoreMenuItemDelete(data: {hfid: ["Campus", "WirelessMenu"]}) { ok }
}
```
"""

# Purge-and-reload, targets passed as variables from a json fence (one as the
# whole ``data`` input), a query block ahead of it, comments inside the
# mutation, and a continued ``console`` command.
REMOVE_APPLY_PASS_VARIANT = """\
Check what is there first:

```graphql
query { CoreMenuItem(namespace__value: "Campus") { edges { node { name { value } } } } }
```

Purge the project's namespace, then reload.

```graphql
# purge everything under Campus, children before headers
mutation Purge($f: [String!]!, $ap: [String!]!, $c: [String!]!, $b: [String!]!, $sw: [String!]!, $w: GenericDeleteInput!, $s: [String!]!, $x: [String!]!) {
  a: CoreMenuItemDelete(data: {hfid: $f}) { ok }
  b: CoreMenuItemDelete(data: {hfid: $ap}) { ok }
  c: CoreMenuItemDelete(data: {hfid: $c}) { ok }
  d: CoreMenuItemDelete(data: {hfid: $b}) { ok }
  e: CoreMenuItemDelete(data: {hfid: $sw}) { ok }
  f: CoreMenuItemDelete(data: $w) { ok }
  g: CoreMenuItemDelete(data: {hfid: $s}) { ok }
  h: CoreMenuItemDelete(data: {hfid: $x}) { ok }
}
```

```json
{
  "variables": {
    "f": ["Campus", "FloorMenu"],
    "ap": ["Campus", "AccessPointMenu"],
    "c": ["Campus", "ControllerMenu"],
    "b": ["Campus", "BuildingMenu"],
    "sw": ["Campus", "SwitchMenu"],
    "w": {"hfid": ["Campus", "WirelessMenu"]},
    "s": ["Campus", "SitesMenu"],
    "x": ["Campus", "SwitchingMenu"]
  }
}
```

```console
$ infrahubctl menu load \\
    menus/campus.yml --branch main
```
"""

REMOVE_APPLY_FAIL = """\
Reload the menu and the sidebar follows the file:

```bash
infrahubctl menu load menus/campus.yml
```
"""

# Names CoreMenuItemDelete in prose and in comments, and deletes the Wireless
# header on the belief that its children go with it; they do not.
REMOVE_APPLY_FAIL_NEARMISS = """\
Reload, then delete the retired section with CoreMenuItemDelete; its entries go with it.

```bash
infrahubctl menu load menus/campus.yml
```

```graphql
mutation {
  CoreMenuItemDelete(data: {hfid: ["Campus", "FloorMenu"]}) { ok }
  CoreMenuItemDelete(data: {hfid: ["Campus", "WirelessMenu"]}) { ok }
  # CoreMenuItemDelete(data: {hfid: ["Campus", "AccessPointMenu"]}) { ok }
  # CoreMenuItemDelete(data: {hfid: ["Campus", "ControllerMenu"]}) { ok }
}
```

Not needed: `CoreMenuItemDelete(data: {hfid: ["Campus", "AccessPointMenu"]})`.
"""

REMOVE_IDS = frozenset(
    {
        ("Campus", "FloorMenu"),
        ("Campus", "WirelessMenu"),
        ("Campus", "AccessPointMenu"),
        ("Campus", "ControllerMenu"),
    }
)
KEEP_IDS = frozenset(
    {
        ("Campus", "SitesMenu"),
        ("Campus", "BuildingMenu"),
        ("Campus", "SwitchingMenu"),
        ("Campus", "SwitchMenu"),
    }
)

_TARGETED_DELETES = """\
```graphql
mutation {
  a: CoreMenuItemDelete(data: {hfid: ["Campus", "FloorMenu"]}) { ok }
  b: CoreMenuItemDelete(data: {hfid: ["Campus", "AccessPointMenu"]}) { ok }
  c: CoreMenuItemDelete(data: {hfid: ["Campus", "ControllerMenu"]}) { ok }
  d: CoreMenuItemDelete(data: {hfid: ["Campus", "WirelessMenu"]}) { ok }
}
```
"""

_PURGE_KEPT = """\
```graphql
mutation {
  CoreMenuItemDelete(data: {hfid: ["Campus", "SwitchMenu"]}) { ok }
}
```
"""

_LOAD = """\
```bash
infrahubctl menu load menus/campus.yml
```
"""


class TestRemovedItemsChecks:
    def _deleted(self, apply_md: str):
        doc = yaml.safe_load(REMOVE_MENU_KEPT)
        return CHECKS["removed-items-deleted"](
            doc, apply_raw=apply_md, removed_ids=REMOVE_IDS, kept_ids=KEEP_IDS
        )

    @pytest.mark.parametrize(
        ("apply_md", "should_pass"),
        [
            (REMOVE_APPLY_PASS, True),
            (REMOVE_APPLY_PASS_VARIANT, True),
            (REMOVE_APPLY_FAIL, False),
            (REMOVE_APPLY_FAIL_NEARMISS, False),
        ],
        ids=["pass", "pass-variant", "fail", "fail-nearmiss"],
    )
    def test_four_fixtures(self, apply_md, should_pass):
        ok, msg = self._deleted(apply_md)
        assert ok is should_pass, msg

    def test_nearmiss_names_the_uncascaded_children(self):
        ok, msg = self._deleted(REMOVE_APPLY_FAIL_NEARMISS)
        assert not ok
        assert "[Campus, AccessPointMenu]" in msg
        assert "[Campus, ControllerMenu]" in msg
        assert "[Campus, WirelessMenu]" not in msg

    def test_builtin_delete_fails(self):
        apply_md = _LOAD + _TARGETED_DELETES + (
            '```graphql\nmutation { CoreMenuItemDelete(data: {hfid: ["Builtin", "IPAM"]}) { ok } }\n```\n'
        )
        ok, msg = self._deleted(apply_md)
        assert not ok
        assert "protected built-in" in msg

    def test_purging_kept_item_without_reload_fails(self):
        ok, msg = self._deleted(_TARGETED_DELETES + _PURGE_KEPT)
        assert not ok
        assert "[Campus, SwitchMenu]" in msg

    def test_reload_before_purge_does_not_restore(self):
        ok, msg = self._deleted(_LOAD + _TARGETED_DELETES + _PURGE_KEPT)
        assert not ok
        assert "no later infrahubctl menu load" in msg

    def test_reload_later_in_the_same_fence_restores(self):
        notes = """\
```bash
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
infrahubctl object delete CoreMenuItem Campus/AccessPointMenu --yes
infrahubctl object delete CoreMenuItem Campus/ControllerMenu --yes
infrahubctl object delete CoreMenuItem Campus/WirelessMenu --yes
infrahubctl object delete CoreMenuItem Campus/SwitchMenu --yes
infrahubctl menu load menus/campus.yml
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_reload_earlier_in_the_same_fence_does_not_restore(self):
        notes = """\
```bash
infrahubctl menu load menus/campus.yml
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
infrahubctl object delete CoreMenuItem Campus/AccessPointMenu --yes
infrahubctl object delete CoreMenuItem Campus/ControllerMenu --yes
infrahubctl object delete CoreMenuItem Campus/WirelessMenu --yes
infrahubctl object delete CoreMenuItem Campus/SwitchMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "no later infrahubctl menu load" in msg

    def test_reload_after_purge_restores(self):
        ok, msg = self._deleted(_TARGETED_DELETES + _PURGE_KEPT + _LOAD)
        assert ok, msg

    def test_id_delete_is_reported_unresolved(self):
        apply_md = '```graphql\nmutation { CoreMenuItemDelete(data: {id: "1813"}) { ok } }\n```\n'
        ok, msg = self._deleted(apply_md)
        assert not ok
        assert "unresolved deletes" in msg

    def test_delete_outside_a_fence_does_not_count(self):
        apply_md = _TARGETED_DELETES.replace("```graphql\n", "").replace("```\n", "")
        ok, _ = self._deleted(apply_md)
        assert not ok

    def test_curl_payload_counts(self):
        body = json.dumps(
            {
                "query": "mutation($f: [String!]!) { a: CoreMenuItemDelete(data: {hfid: $f}) { ok } "
                'b: CoreMenuItemDelete(data: {hfid: ["Campus", "WirelessMenu"]}) { ok } '
                'c: CoreMenuItemDelete(data: {hfid: ["Campus", "AccessPointMenu"]}) { ok } '
                'd: CoreMenuItemDelete(data: {hfid: ["Campus", "ControllerMenu"]}) { ok } }',
                "variables": {"f": ["Campus", "FloorMenu"]},
            }
        )
        apply_md = (
            "```bash\ncurl -s -X POST \"$INFRAHUB_ADDRESS/graphql\" \\\n"
            f"  -H 'Content-Type: application/json' --data-raw '{body}'\n```\n"
        )
        ok, msg = self._deleted(apply_md)
        assert ok, msg

    def test_ctl_object_delete_counts(self):
        apply_md = """\
```bash
cp output.yml menus/campus.yml
infrahubctl object delete CoreMenuItem Campus/AccessPointMenu --yes
infrahubctl object delete CoreMenuItem Campus/ControllerMenu --yes
infrahubctl object delete --branch main CoreMenuItem Campus/WirelessMenu -y
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
infrahubctl menu load menus/campus.yml
```
"""
        ok, msg = self._deleted(apply_md)
        assert ok, msg

    def test_ctl_object_delete_of_another_kind_does_not_count(self):
        def script(kind: str) -> str:
            lines = "".join(
                f"infrahubctl object delete {kind} Campus/{name} --yes\n"
                for name in ("FloorMenu", "WirelessMenu", "AccessPointMenu", "ControllerMenu")
            )
            return f"```bash\n{lines}```\n"

        assert self._deleted(script("CoreMenuItem"))[0]
        ok, _ = self._deleted(script("CampusFloor"))
        assert not ok

    def test_untagged_fence_counts(self):
        ok, msg = self._deleted(_TARGETED_DELETES.replace("```graphql", "```"))
        assert ok, msg

    def test_dropped_check_catches_leftover_and_lost_items(self):
        doc = yaml.safe_load(REMOVE_MENU_KEPT)
        ok, _ = CHECKS["removed-items-dropped"](doc, removed_ids=REMOVE_IDS, kept_ids=KEEP_IDS)
        assert ok
        leftover = REMOVE_IDS | {("Campus", "SitesMenu")}
        ok, msg = CHECKS["removed-items-dropped"](
            doc, removed_ids=leftover, kept_ids=KEEP_IDS - {("Campus", "SitesMenu")}
        )
        assert not ok
        assert "[Campus, SitesMenu]" in msg
        ok, msg = CHECKS["removed-items-dropped"](
            doc, removed_ids=REMOVE_IDS, kept_ids=KEEP_IDS | {("Campus", "FloorMenu")}
        )
        assert not ok
        assert "missing from the menu file" in msg


# The menu file is git-synced; LabMenu was loaded by hand and never committed.
SYNC_NOTES_PASS = """\
```bash
cp output.yml menus/campus.yml
git add menus/campus.yml
git commit -m "Retire wireless and floors from the sidebar"
git push origin main
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""

# The sync-owned items are named only in prose, the git steps sit in an
# untagged fence, and LabMenu goes through a JSON request body with variables.
SYNC_NOTES_PASS_VARIANT = """\
Leave `infrahubctl object delete CoreMenuItem Campus/WirelessMenu` alone: the
sync deletes the items it loaded and no longer finds.

```
git commit -am "Retire wireless and floors" && git push
```

```json
{
  "query": "mutation Lab($h: [String!]!) { CoreMenuItemDelete(data: {hfid: $h}) { ok } }",
  "variables": {"h": ["Campus", "LabMenu"]}
}
```
"""

SYNC_NOTES_FAIL = """\
```bash
git commit -am "Retire wireless and floors" && git push
infrahubctl object delete CoreMenuItem Campus/AccessPointMenu --yes
infrahubctl object delete CoreMenuItem Campus/ControllerMenu --yes
infrahubctl object delete CoreMenuItem Campus/WirelessMenu --yes
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""

# Names the Lab delete in a comment and in prose, and never runs it.
SYNC_NOTES_FAIL_NEARMISS = """\
Push, then delete LabMenu with CoreMenuItemDelete.

```bash
git commit -am "Retire wireless and floors" && git push
# infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""


class TestRemoveSyncedItemsTask:
    def _deleted(self, notes_md: str):
        doc = yaml.safe_load(REMOVE_MENU_KEPT)
        return CHECKS["removed-items-deleted"](
            doc,
            apply_raw=notes_md,
            removed_ids=REMOVE_IDS,
            kept_ids=KEEP_IDS,
            hand_delete_ids=frozenset({("Campus", "LabMenu")}),
            sync_removed_ids=REMOVE_IDS,
        )

    def test_hand_deleting_sync_owned_items_fails(self):
        ok, msg = self._deleted(SYNC_NOTES_FAIL)
        assert not ok
        assert "the git sync removes on its own" in msg
        assert "[Campus, WirelessMenu]" in msg

    def test_commented_lab_delete_does_not_count(self):
        ok, msg = self._deleted(SYNC_NOTES_FAIL_NEARMISS)
        assert not ok
        assert "[Campus, LabMenu]" in msg

    def test_id_deletes_beyond_the_hand_loaded_item_fail(self):
        """The red-run shape: every item deleted by an id the grader cannot resolve."""
        lines = "".join(
            f"infrahubctl object delete CoreMenuItem <{name}-id>\n"
            for name in ("AccessPointMenu", "ControllerMenu", "WirelessMenu", "FloorMenu", "LabMenu")
        )
        ok, msg = self._deleted(f"```bash\ngit commit -am 'Retire wireless' && git push origin main\n{lines}```\n")
        assert not ok
        assert "the git sync removes on its own" in msg
        assert "[Campus, WirelessMenu]" in msg

    def test_id_deletes_of_synced_items_beside_an_hfid_lab_delete_fail(self):
        lines = "".join(
            f"infrahubctl object delete CoreMenuItem <{name}-id>\n"
            for name in ("AccessPointMenu", "ControllerMenu", "WirelessMenu", "FloorMenu")
        )
        lines += "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n"
        ok, msg = self._deleted(f"```bash\ngit commit -am 'Retire wireless' && git push origin main\n{lines}```\n")
        assert not ok
        assert "the git sync removes on its own" in msg
        assert "[Campus, LabMenu]" not in msg

    def test_shell_loop_targets_are_unrolled_and_rejected(self):
        """A loop over ``Campus/$n`` is unrolled, so each target resolves to a synced item."""
        notes = """\
```bash
git commit -am 'Retire wireless' && git push origin main
for n in FloorMenu WirelessMenu; do infrahubctl object delete CoreMenuItem "Campus/$n" --yes; done
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu], [Campus, WirelessMenu]" in msg

    def test_unexpanded_variable_beyond_the_needed_deletes_fails(self):
        notes = """\
```bash
git commit -am 'Retire wireless' && git push origin main
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
infrahubctl object delete CoreMenuItem "Campus/$ITEM" --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "Campus/$ITEM" in msg

    def test_placeholder_never_satisfies_the_required_delete(self):
        for target in ("Campus/<LabMenu>", "Campus/{}", "<ns>/LabMenu"):
            notes = (
                "```bash\ngit commit -am 'Retire wireless' && git push origin main\n"
                f"infrahubctl object delete CoreMenuItem {target} --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert not ok, target
            assert "[Campus, LabMenu]" in msg, target

    def test_placeholder_naming_a_synced_item_counts_as_deleting_it(self):
        notes = (
            "```bash\ngit commit -am 'Retire wireless' && git push origin main\n"
            "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n"
            "infrahubctl object delete CoreMenuItem Campus/<FloorMenu> --yes\n```\n"
        )
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_placeholder_for_unknown_children_is_ignored(self):
        """The trial shape: delete Lab, plus a template for any children it has."""
        notes = """\
```bash
git commit -am 'Retire wireless' && git push origin main
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
# only if Lab had entries nested under it:
infrahubctl object delete CoreMenuItem Campus/<ChildName> --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_reload_instead_of_push_fails(self):
        """A menu load runs no sync, so the dropped file items stay."""
        notes = """\
```bash
infrahubctl menu load output.yml
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_push_inside_a_chained_command_counts(self):
        notes = """\
```bash
git add menus/campus.yml && git -C . commit -m "Retire wireless" && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_indented_fences_under_a_numbered_list_count(self):
        notes = """\
1. Push the change:

   ```bash
   git commit -am 'Retire wireless' && git push origin main
   ```

2. Delete the hand-loaded entry:

   ```bash
   infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
   ```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_shorter_backtick_run_does_not_close_a_longer_fence(self):
        notes = """\
````markdown
```bash
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
```
````

```bash
git commit -am 'Retire wireless' && git push origin main
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_echoed_commands_do_not_run(self):
        notes = """\
```bash
echo git commit -am retire && echo git push
echo infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_echoed_delete_of_a_synced_item_is_not_a_delete(self):
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
echo "not needed:" infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_git_push_must_be_the_subcommand(self):
        for push_like in ("git stash push", "git commit -m push", "git archive --prefix push HEAD"):
            notes = (
                "```bash\ngit commit -am retire\n"
                f"{push_like}\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert not ok, push_like
            assert "No git push" in msg, push_like

    def test_git_global_options_before_push_count(self):
        notes = (
            "```bash\ngit -C repo commit -am retire\n"
            "git -C repo -c push.default=current push\n"
            "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
        )
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_push_without_commit_fails(self):
        notes = (
            "```bash\ngit push origin main\n"
            "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
        )
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git commit before the push" in msg

    def test_commit_after_the_push_does_not_count(self):
        notes = (
            "```bash\ngit push origin main\ngit commit -am retire\n"
            "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
        )
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git commit before the push" in msg

    def test_longer_closing_fence_closes(self):
        notes = (
            "```bash\ngit commit -am retire && git push\n"
            "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n````\n"
        )
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_launcher_wrapped_lab_delete_counts(self):
        """``uv run infrahubctl`` is the form infrahub-common teaches."""
        for launcher in ("uv run", "uv run --with infrahub-sdk", "poetry run", "pipx run"):
            notes = (
                "```bash\ngit commit -am retire && git push\n"
                f"{launcher} infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{launcher}: {msg}"

    def test_launcher_wrapped_delete_of_a_synced_item_fails(self):
        notes = (
            "```bash\ngit commit -am retire && git push\n"
            "uv run infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n"
            "sudo -u bot env INFRAHUB_ADDRESS=x uv run infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes\n```\n"
        )
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_wrapped_git_push_counts(self):
        for push in ("(cd repo && git commit -am retire && git push)", "env GIT_SSH_COMMAND=ssh git commit -am retire && env X=y git push", "sudo -u bot git commit -am retire; sudo git push"):
            notes = (
                f"```bash\n{push}\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{push}: {msg}"

    def test_wrapper_flags_do_not_swallow_the_program(self):
        """``sudo -S`` is a flag, so ``git`` after it is still the program."""
        for push in ("sudo -S git commit -am retire && sudo -S git push", "sudo -E -n git commit -am retire && sudo -E -u bot git push", "env -i PATH=/usr/bin git commit -am retire && env -i git push"):
            notes = (
                f"```bash\n{push}\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{push}: {msg}"

    def test_launcher_options_before_run_are_peeled(self):
        for launcher in ("uv --directory repo run", "uv --color never run --frozen", "poetry -C repo run", "poetry --directory=repo run"):
            notes = (
                "```bash\ngit commit -am retire && git push\n"
                f"{launcher} infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{launcher}: {msg}"

    def test_launcher_without_run_is_not_peeled(self):
        notes = (
            "```bash\ngit commit -am retire && git push\n"
            "uv sync infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
        )
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, LabMenu]" in msg

    def test_apostrophe_in_echo_prose_does_not_hide_a_synced_delete(self):
        """Two ``Lab's``-style apostrophes must not pair up across the delete."""
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
echo Lab's gone
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
echo Floor's gone
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_apostrophe_in_a_heredoc_message_keeps_the_push(self):
        notes = """\
```bash
git commit -F - <<'EOF'
Retire wireless and floors

what's dropped is left to the sync
EOF
git push origin main
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_heredoc_body_is_not_run(self):
        notes = """\
```bash
cat > steps.txt <<EOF
git commit -am retire && git push
EOF
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_quoted_or_commented_heredoc_marker_opens_no_heredoc(self):
        """``<<EOF`` inside quotes or a comment must not swallow the commands after it."""
        for marker in ("echo '<<EOF'", 'echo "write <<EOF to open one"', "cat notes.txt  # <<EOF", "cat <<<EOF"):
            notes = (
                f"```bash\n{marker}\n"
                "git commit -am retire && git push\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{marker}: {msg}"

    def test_quoted_heredoc_marker_does_not_hide_a_synced_delete(self):
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
echo '<<EOF'
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_escaped_space_before_hash_keeps_the_heredoc(self):
        """In ``notes\\ #`` the space is escaped, so ``#`` is text and ``<<EOF`` opens a heredoc."""
        notes = r"""```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
cat > notes\ # <<EOF
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_escaped_backslash_before_space_still_starts_a_comment(self):
        """In ``x\\\\ #`` the backslash is escaped, the space is real, so ``#`` starts a comment."""
        notes = r"""```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
echo x\\ # <<EOF
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_heredoc_fed_to_a_shell_runs_its_commands(self):
        """A body piped into ``sh`` runs, so a synced-item delete inside it counts."""
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
docker compose exec -T infrahub-server sh <<'EOF'
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_heredoc_over_ssh_runs_the_lab_delete(self):
        notes = """\
```bash
git commit -am retire && git push
ssh infrahub-host <<EOF
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_console_heredoc_terminator_behind_a_prompt(self):
        """In a console fence the terminator reads ``> EOF``."""
        notes = """\
```console
$ git commit -F - <<'EOF'
> Retire wireless and floors; what's dropped is left to the sync
> EOF
$ git push origin main
$ infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_heredoc_written_to_a_file_named_bash_stays_data(self):
        """``cat > bash`` writes a file; ``bash`` here is a filename, not a shell."""
        notes = """\
```bash
cat > bash <<'EOF'
git commit -am retire && git push
EOF
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_heredoc_to_a_remote_file_over_ssh_stays_data(self):
        """``ssh host 'cat > apply.sh'`` stores the body; it does not run it."""
        notes = """\
```bash
ssh infrahub-host 'cat > apply.sh' <<'EOF'
git commit -am retire && git push
EOF
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_heredoc_to_a_remote_shell_runs(self):
        notes = """\
```bash
git commit -am retire && git push
ssh -p 2222 infrahub-host bash -s <<'EOF'
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_heredoc_piped_through_cat_into_a_shell_runs(self):
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
cat <<'EOF' | sh
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_prompt_shaped_line_does_not_end_a_heredoc_outside_console(self):
        """In a bash fence ``> EOF`` is body text; only ``EOF`` ends the heredoc."""
        notes = """\
```bash
cat > notes.txt <<'EOF'
> EOF
git commit -am retire && git push
EOF
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_exec_without_stdin_flag_does_not_run_the_heredoc(self):
        """Without ``-i`` the body never reaches the shell, so the Lab delete does not happen."""
        for wrapper in ("docker exec infrahub-server sh", "podman exec infrahub-server sh", "kubectl exec infrahub-0 -- sh"):
            notes = (
                "```bash\ngit commit -am retire && git push\n"
                f"{wrapper} <<'EOF'\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\nEOF\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert not ok, wrapper
            assert "[Campus, LabMenu]" in msg, wrapper

    def test_exec_with_stdin_flag_runs_the_heredoc(self):
        for wrapper in ("docker exec -i infrahub-server sh", "podman exec --interactive infrahub-server sh", "kubectl exec -it infrahub-0 -- sh", "docker-compose exec -T infrahub-server sh"):
            notes = (
                "```bash\ngit commit -am retire && git push\n"
                f"{wrapper} <<'EOF'\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\nEOF\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{wrapper}: {msg}"

    def test_explicit_stdin_descriptor_heredoc_runs(self):
        """``bash 0<<'EOF'`` runs the body; a synced-item delete inside it counts."""
        for operator in ("0<<'EOF'", "0<<-EOF"):
            notes = (
                "```bash\ngit commit -am retire && git push\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n"
                f"bash {operator}\n"
                "infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes\nEOF\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert not ok, operator
            assert "[Campus, FloorMenu]" in msg, operator

    def test_heredoc_on_another_descriptor_stays_data(self):
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
bash 3<<'EOF'
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_bundled_s_option_reads_the_heredoc(self):
        """``bash -es -- ignored`` reads stdin; ``ignored`` is a positional argument."""
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
bash -es -- ignored <<'EOF'
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "[Campus, FloorMenu]" in msg

    def test_c_option_wins_over_s_wherever_it_sits(self):
        """With ``-c`` the commands come from its string, so the heredoc stays data."""
        for shell in ("bash -sc 'cat > /tmp/steps'", "bash -s -c 'cat > /tmp/steps'", "bash -cs 'cat > /tmp/steps'"):
            notes = (
                "```bash\ngit commit -am retire && git push\n"
                "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n"
                f"{shell} <<'EOF'\n"
                "infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes\nEOF\n```\n"
            )
            ok, msg = self._deleted(notes)
            assert ok, f"{shell}: {msg}"

    def test_lone_dash_reads_stdin_only_without_a_script(self):
        """``bash -`` runs the heredoc; ``bash - script.sh`` runs the file instead."""
        runs = (
            "```bash\ngit commit -am retire && git push\n"
            "infrahubctl object delete CoreMenuItem Campus/LabMenu --yes\n"
            "bash - <<'EOF'\n"
            "infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes\nEOF\n```\n"
        )
        ok, msg = self._deleted(runs)
        assert not ok
        assert "[Campus, FloorMenu]" in msg
        ok, msg = self._deleted(runs.replace("bash - <<", "bash - apply.sh <<"))
        assert ok, msg

    def test_bundled_c_option_leaves_the_heredoc_as_data(self):
        notes = """\
```bash
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
bash -ec 'cat > /tmp/steps' <<'EOF'
infrahubctl object delete CoreMenuItem Campus/FloorMenu --yes
EOF
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_heredoc_fed_to_python_stays_data(self):
        notes = """\
```bash
python - <<'EOF'
print("git commit -am retire && git push")
EOF
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert not ok
        assert "No git push" in msg

    def test_quote_never_closed_falls_back_to_line_by_line(self):
        notes = """\
```bash
echo 'start of a note that never ends
git commit -am retire && git push
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_multi_line_commit_message_keeps_the_commit(self):
        notes = """\
```bash
git commit -am "Retire wireless and floors

The sync removes the dropped entries; Lab goes by hand."
git push origin main
infrahubctl object delete CoreMenuItem Campus/LabMenu --yes
```
"""
        ok, msg = self._deleted(notes)
        assert ok, msg

    def test_task_script_scores_four_fixtures(self, tmp_path):
        """The task grader scores the four fixtures 1.0 / 1.0 / <1.0 / <1.0."""
        cases = [
            ("pass", SYNC_NOTES_PASS, True),
            ("pass-variant", SYNC_NOTES_PASS_VARIANT, True),
            ("fail", SYNC_NOTES_FAIL, False),
            ("fail-nearmiss", SYNC_NOTES_FAIL_NEARMISS, False),
        ]
        for name, notes_md, should_pass in cases:
            workdir = tmp_path / name
            workdir.mkdir()
            (workdir / "output.yml").write_text(REMOVE_MENU_KEPT)
            (workdir / "notes.md").write_text(notes_md)
            result = subprocess.run(
                [sys.executable, str(_GRADERS_DIR / "check_remove_synced_items.py")],
                capture_output=True,
                text=True,
                cwd=workdir,
            )
            assert result.returncode == 0, result.stderr
            score = json.loads(result.stdout)["score"]
            if should_pass:
                assert score == 1.0, f"{name}: {result.stdout}"
            else:
                assert score < 1.0, f"{name} scored 1.0: {result.stdout}"


class TestShellParserEdgeCases:
    """Regressions for the apply-step shell and GraphQL readers."""

    def test_loop_value_with_backslash_does_not_crash(self):
        commands = _mod._shell_commands("for i in 'a\\1' b; do echo $i; done")
        # The value is substituted as text, not as a re.sub template.
        assert [argv[0] for argv in commands] == ["echo", "echo"]
        assert commands[1] == ["echo", "b"]

    def test_curl_payload_in_untagged_fence_is_read(self):
        text = (
            "```\n"
            "curl -X POST http://localhost:8000/graphql -d "
            '\'{"query": "mutation { CoreMenuItemDelete(data: {hfid: [\\"Campus\\", '
            '\\"LabMenu\\"]}) { ok } }"}\'\n'
            "```\n"
        )
        deletes, _, _ = _mod._menu_item_deletes(text)
        assert [hfid for _, hfid in deletes] == [("Campus", "LabMenu")]

    def test_lone_dash_shell_runs_heredoc(self):
        commands = _mod._shell_commands("sh - <<'EOF'\ngit push\nEOF")
        assert ["git", "push"] in commands

    def test_heredoc_written_inside_running_heredoc_is_data(self):
        body = "ssh host <<'EOF'\ncat > /tmp/x <<'IN'\ngit push\nIN\nEOF"
        assert ["git", "push"] not in _mod._shell_commands(body)

    def test_attached_option_value_is_not_a_flag(self):
        body = "docker exec -uinfrahub server sh <<'EOF'\ngit push\nEOF"
        assert ["git", "push"] not in _mod._shell_commands(body)
        body = "docker exec -iuinfrahub server sh <<'EOF'\ngit push\nEOF"
        assert ["git", "push"] in _mod._shell_commands(body)
