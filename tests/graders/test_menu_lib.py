"""Tests for skills/menu-creator/graders/lib.py.

Covers >= 8 check functions against both good and bad menu YAML.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Load the module directly — the hyphenated directory is not a valid Python
# package name, so we use importlib.util to load lib.py by file path.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "skills" / "menu-creator" / "graders" / "lib.py"
_spec = importlib.util.spec_from_file_location("menu_creator_graders_lib", _LIB_PATH)
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
load_output = _mod.load_output
run_checks = _mod.run_checks

_GRADERS_DIR = _REPO_ROOT / "skills" / "menu-creator" / "graders"


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

    def test_all_scripts_output_valid_json(self, tmp_path):
        scripts = ["check_flat_menu.py", "check_hierarchical.py", "check_generic_kind.py"]
        for script in scripts:
            result = self._run_script(script, str(tmp_path / "missing.yml"))
            # Must be valid JSON with required keys
            assert isinstance(result.get("score"), float)
            assert isinstance(result.get("details"), str)
            assert isinstance(result.get("checks"), list)
