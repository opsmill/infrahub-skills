"""Tests for the thin grader scripts in skills/schema-creator/graders/.

Covers:
- check_vlan.py
- check_circuit.py
- check_location.py

Each test verifies:
1. The script outputs valid JSON when no output file exists (score 0.0)
2. The script outputs score 1.0 when given a correct schema
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADERS_DIR = _REPO_ROOT / "skills" / "schema-creator" / "graders"


def _run_grader(script_name: str, cwd: Path) -> dict:
    """Run a grader script and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, str(_GRADERS_DIR / script_name)],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    assert result.returncode == 0, (
        f"{script_name} exited with code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"{script_name} did not output valid JSON:\n{result.stdout}"
        ) from exc


def _assert_skillgrade_shape(data: dict) -> None:
    """Assert that a dict has the skillgrade JSON shape."""
    assert "score" in data, "Missing 'score' key"
    assert "details" in data, "Missing 'details' key"
    assert "checks" in data, "Missing 'checks' key"
    assert isinstance(data["score"], float), f"score is not float: {data['score']!r}"
    assert 0.0 <= data["score"] <= 1.0, f"score out of range: {data['score']}"
    assert isinstance(data["checks"], list), "checks is not a list"
    for entry in data["checks"]:
        assert "name" in entry
        assert "passed" in entry
        assert "message" in entry


# ---------------------------------------------------------------------------
# Correct schema fixtures
# ---------------------------------------------------------------------------

GOOD_VLAN_SCHEMA = {
    "version": "1.0",
    "nodes": [
        {
            "name": "VLAN",
            "namespace": "Ipam",
            "display_label": "{{ vlan_id__value }} - {{ name__value }}",
            "human_friendly_id": ["vlan_id__value"],
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "vlan_id", "kind": "Number"},
                {
                    "name": "status",
                    "kind": "Dropdown",
                    "choices": [
                        {"name": "active", "label": "Active"},
                        {"name": "reserved", "label": "Reserved"},
                        {"name": "deprecated", "label": "Deprecated"},
                    ],
                },
            ],
            "relationships": [
                {
                    "name": "group",
                    "peer": "IpamVlanGroup",
                    "kind": "Attribute",
                    "identifier": "vlangroup__vlans",
                    "cardinality": "one",
                },
            ],
        },
        {
            "name": "VlanGroup",
            "namespace": "Ipam",
            "display_label": "{{ name__value }}",
            "human_friendly_id": ["name__value"],
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {
                    "name": "vlans",
                    "peer": "IpamVLAN",
                    "kind": "Attribute",
                    "identifier": "vlangroup__vlans",
                    "cardinality": "many",
                },
            ],
        },
    ],
    "generics": [],
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

GOOD_LOCATION_SCHEMA = {
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


# ---------------------------------------------------------------------------
# check_vlan.py tests
# ---------------------------------------------------------------------------


class TestCheckVlan:
    def test_outputs_valid_json_no_output_file(self, tmp_path):
        """Score is 0.0 when output.yml does not exist."""
        data = _run_grader("check_vlan.py", tmp_path)
        _assert_skillgrade_shape(data)
        assert data["score"] == 0.0

    def test_score_1_with_correct_schema(self, tmp_path):
        """Score is 1.0 when output.yml is a correct VLAN schema."""
        output_file = tmp_path / "output.yml"
        output_file.write_text(yaml.dump(GOOD_VLAN_SCHEMA))
        data = _run_grader("check_vlan.py", tmp_path)
        _assert_skillgrade_shape(data)
        assert data["score"] == 1.0, (
            f"Expected score 1.0 but got {data['score']}. Details: {data['details']}\n"
            f"Checks: {data['checks']}"
        )

    def test_check_names_in_output(self, tmp_path):
        """Output includes all expected check names."""
        data = _run_grader("check_vlan.py", tmp_path)
        check_names = {c["name"] for c in data["checks"]}
        expected = {
            "attr-min-length",
            "dropdown-for-status",
            "no-deprecated-string",
            "full-kind-references",
            "human-friendly-id",
            "display-label-singular",
            "schema-version",
        }
        assert expected == check_names, f"Unexpected check names: {check_names}"


# ---------------------------------------------------------------------------
# check_circuit.py tests
# ---------------------------------------------------------------------------


class TestCheckCircuit:
    def test_outputs_valid_json_no_output_file(self, tmp_path):
        """Score is 0.0 when output.yml does not exist."""
        data = _run_grader("check_circuit.py", tmp_path)
        _assert_skillgrade_shape(data)
        assert data["score"] == 0.0

    def test_score_1_with_correct_schema(self, tmp_path):
        """Score is 1.0 when output.yml is a correct circuit schema."""
        output_file = tmp_path / "output.yml"
        output_file.write_text(yaml.dump(GOOD_CIRCUIT_SCHEMA))
        data = _run_grader("check_circuit.py", tmp_path)
        _assert_skillgrade_shape(data)
        assert data["score"] == 1.0, (
            f"Expected score 1.0 but got {data['score']}. Details: {data['details']}\n"
            f"Checks: {data['checks']}"
        )

    def test_check_names_in_output(self, tmp_path):
        """Output includes all expected check names."""
        data = _run_grader("check_circuit.py", tmp_path)
        check_names = {c["name"] for c in data["checks"]}
        expected = {
            "attribute-kind-relationships",
            "endpoint-device-relationship",
            "two-endpoint-relationships",
            "matching-identifiers",
            "full-kind-references",
            "human-friendly-id",
        }
        assert expected == check_names, f"Unexpected check names: {check_names}"


# ---------------------------------------------------------------------------
# check_location.py tests
# ---------------------------------------------------------------------------


class TestCheckLocation:
    def test_outputs_valid_json_no_output_file(self, tmp_path):
        """Score is 0.0 when output.yml does not exist."""
        data = _run_grader("check_location.py", tmp_path)
        _assert_skillgrade_shape(data)
        assert data["score"] == 0.0

    def test_score_1_with_correct_schema(self, tmp_path):
        """Score is 1.0 when output.yml is a correct location schema."""
        output_file = tmp_path / "output.yml"
        output_file.write_text(yaml.dump(GOOD_LOCATION_SCHEMA))
        data = _run_grader("check_location.py", tmp_path)
        _assert_skillgrade_shape(data)
        assert data["score"] == 1.0, (
            f"Expected score 1.0 but got {data['score']}. Details: {data['details']}\n"
            f"Checks: {data['checks']}"
        )

    def test_check_names_in_output(self, tmp_path):
        """Output includes all expected check names."""
        data = _run_grader("check_location.py", tmp_path)
        check_names = {c["name"] for c in data["checks"]}
        expected = {
            "hierarchical-generic",
            "inherit-from-generic",
            "root-no-parent",
            "human-friendly-id",
            "display-label-singular",
            "schema-version",
            "correct-hierarchy-chain",
        }
        assert expected == check_names, f"Unexpected check names: {check_names}"
