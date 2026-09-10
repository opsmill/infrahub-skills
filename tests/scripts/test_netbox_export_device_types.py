"""Tests for the NetBox live-instance exporter.

Fixtures are trimmed from real responses captured from the public NetBox
demo (demo.netbox.dev), so the shapes here are the shapes NetBox actually
returns rather than a guess at them: choice fields as ``{value, label}``,
related objects as nested documents, and unset fields as ``null``.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = (
    _REPO_ROOT
    / "skills"
    / "infrahub-converting-netbox-device-types"
    / "scripts"
    / "netbox_export_device_types.py"
)

_spec = importlib.util.spec_from_file_location("netbox_export_device_types", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["netbox_export_device_types"] = _mod
_spec.loader.exec_module(_mod)

ExportError = _mod.ExportError
as_number = _mod.as_number
build_document = _mod.build_document
carry_fields = _mod.carry_fields
export = _mod.export
is_present = _mod.is_present
main = _mod.main
missing_required = _mod.missing_required
output_path = _mod.output_path
paginate = _mod.paginate
port_mappings = _mod.port_mappings
render_document = _mod.render_document
unwrap = _mod.unwrap


# ---------------------------------------------------------------------------
# Fixtures shaped like real NetBox responses
# ---------------------------------------------------------------------------

MANUFACTURER = {"id": 11, "name": "APC", "slug": "apc", "description": ""}

DEVICE_TYPE = {
    "id": 8,
    "manufacturer": MANUFACTURER,
    "model": "AP7901",
    "slug": "ap7901",
    "part_number": "AP7901B",
    "u_height": 1,
    "is_full_depth": False,
    "subdevice_role": None,
    "airflow": None,
    "weight": None,
    "weight_unit": None,
    "front_image": None,
    "rear_image": None,
    "description": "",
    "comments": "",
    "device_count": 15,
}

POWER_PORT = {
    "id": 16,
    "device_type": {"id": 8},
    "name": "Input",
    "label": "",
    "type": None,
    "maximum_draw": None,
    "allocated_draw": None,
    "description": "",
}

POWER_OUTLET = {
    "id": 1,
    "device_type": {"id": 8},
    "name": "Outlet 1",
    "label": "",
    "type": {"value": "nema-5-20r", "label": "NEMA 5-20R"},
    "color": "",
    "power_port": {"id": 16, "name": "Input", "description": ""},
    "feed_leg": None,
    "description": "",
}

INTERFACE = {
    "id": 40,
    "device_type": {"id": 2},
    "name": "GigabitEthernet1/0/1",
    "label": "",
    "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
    "enabled": True,
    "mgmt_only": False,
    "poe_mode": {"value": "pse", "label": "PSE"},
    "poe_type": None,
    "description": "",
}

REAR_PORT = {
    "id": 70,
    "device_type": {"id": 3},
    "name": "Port 1",
    "label": "",
    "type": {"value": "sc", "label": "SC"},
    "positions": 1,
    "color": "",
    "description": "",
}

FRONT_PORT = {
    "id": 90,
    "device_type": {"id": 3},
    "name": "Port 1",
    "label": "",
    "type": {"value": "sc", "label": "SC"},
    "positions": 1,
    "color": "",
    "rear_ports": [{"position": 1, "rear_port": 70, "rear_port_position": 1}],
    "description": "",
}

MODULE_TYPE = {
    "id": 1,
    "manufacturer": {"id": 3, "name": "Juniper", "slug": "juniper"},
    "model": "EX9200-32XS",
    "part_number": "",
    "comments": "32x10GE interfaces",
    "weight": None,
    "weight_unit": None,
}


def make_fetch(tables):
    """Return a fetcher serving canned tables, honouring the id filters."""

    def fetch(endpoint, params):
        rows = list(tables.get(endpoint, []))
        multi = {}
        for key, value in params:
            multi.setdefault(key, []).append(value)
        for key, parent in (
            ("device_type_id", "device_type"),
            ("module_type_id", "module_type"),
        ):
            if key in multi:
                want = {int(v) for v in multi[key]}
                rows = [
                    r
                    for r in rows
                    if isinstance(r.get(parent), dict) and r[parent].get("id") in want
                ]
        limit = int(multi.get("limit", [250])[0])
        offset = int(multi.get("offset", [0])[0])
        page = rows[offset : offset + limit]
        return {
            "count": len(rows),
            "next": (offset + limit) < len(rows),
            "results": page,
        }

    return fetch


# ---------------------------------------------------------------------------
# Value reshaping
# ---------------------------------------------------------------------------


def test_choice_fields_unwrap_to_the_bare_value():
    """NetBox sends {value, label}; the library format wants the value."""
    assert unwrap({"value": "nema-5-20r", "label": "NEMA 5-20R"}) == "nema-5-20r"


def test_related_objects_unwrap_to_their_name():
    assert unwrap({"id": 16, "name": "Input", "description": ""}) == "Input"
    assert unwrap(MANUFACTURER) == "APC"


def test_a_plain_value_passes_through_unwrap():
    for value in ("Port 1", 3, True, None):
        assert unwrap(value) == value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1.5", 1.5), ("2", 2), (2.0, 2), (3, 3), ("", ""), (None, None)],
)
def test_decimal_strings_become_numbers(raw, expected):
    """NetBox may serialize a DecimalField as a string; YAML would quote it."""
    assert as_number(raw) == expected


def test_booleans_survive_number_coercion():
    """bool is an int subclass, so a naive float() would turn False into 0."""
    assert as_number(True) is True
    assert as_number(False) is False


def test_absent_values_are_omitted_but_false_and_zero_are_kept():
    assert not is_present(None)
    assert not is_present("")
    assert not is_present("   ")
    assert not is_present([])
    assert is_present(False)  # is_full_depth: false is meaningful
    assert is_present(0)  # u_height: 0 is meaningful


def test_carry_fields_keeps_declared_order():
    carried = carry_fields(DEVICE_TYPE, ("model", "manufacturer", "slug"))
    assert list(carried) == ["model", "manufacturer", "slug"]


def test_carry_fields_drops_nulls_and_empty_strings():
    carried = carry_fields(DEVICE_TYPE, _mod.DEVICE_TYPE_FIELDS)
    assert "airflow" not in carried
    assert "description" not in carried
    assert carried["is_full_depth"] is False


# ---------------------------------------------------------------------------
# Port mappings
# ---------------------------------------------------------------------------


def test_port_mappings_resolve_primary_keys_to_names():
    mappings = port_mappings([FRONT_PORT], [REAR_PORT])

    assert mappings == [
        {
            "front_port": "Port 1",
            "front_port_position": 1,
            "rear_port": "Port 1",
            "rear_port_position": 1,
        }
    ]


def test_a_mapping_to_an_unknown_rear_port_is_dropped_not_guessed():
    orphan = {**FRONT_PORT, "rear_ports": [{"position": 1, "rear_port": 999}]}

    assert port_mappings([orphan], [REAR_PORT]) == []


def test_no_mappings_when_nothing_is_wired():
    assert port_mappings([{**FRONT_PORT, "rear_ports": []}], [REAR_PORT]) == []


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def test_device_type_document_matches_the_library_shape():
    document, _ = build_document(
        DEVICE_TYPE,
        {"power-ports": [POWER_PORT], "power-outlets": [POWER_OUTLET]},
        is_module=False,
    )

    assert document["manufacturer"] == "APC"
    assert document["slug"] == "ap7901"
    assert document["u_height"] == 1
    assert document["power-outlets"][0]["type"] == "nema-5-20r"
    # The outlet's power_port cross-reference becomes the port's name.
    assert document["power-outlets"][0]["power_port"] == "Input"


def test_a_component_missing_a_schema_required_field_is_reported():
    """Real case: the demo's AP7901 has a power port with no type."""
    _, notes = build_document(
        DEVICE_TYPE, {"power-ports": [POWER_PORT]}, is_module=False
    )

    assert any("unset 'type'" in note for note in notes)
    assert any("library schema requires" in note for note in notes)


def test_a_complete_component_produces_no_note():
    _, notes = build_document(DEVICE_TYPE, {"interfaces": [INTERFACE]}, is_module=False)

    assert notes == []


def test_missing_required_counts_only_the_absent_entries():
    entries = [{"name": "a", "type": "x"}, {"name": "b"}, {"name": "c"}]

    notes = missing_required(entries, "interfaces")

    assert len(notes) == 1
    assert "2 of 3" in notes[0]


def test_module_documents_carry_no_slug_or_rack_geometry():
    document, _ = build_document(
        MODULE_TYPE, {"interfaces": [INTERFACE]}, is_module=True
    )

    assert "slug" not in document
    assert "u_height" not in document
    assert document["model"] == "EX9200-32XS"


def test_a_module_type_rejects_lists_it_cannot_own():
    _, notes = build_document(
        MODULE_TYPE, {"device-bays": [{"name": "Bay 1"}]}, is_module=True
    )

    assert any("device-bays" in note and "module type" in note for note in notes)


def test_a_device_type_missing_a_required_top_level_field_is_reported():
    _, notes = build_document({**DEVICE_TYPE, "slug": ""}, {}, is_module=False)

    assert any("slug" in note and "library schema" in note for note in notes)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def test_documents_render_as_library_yaml():
    text = render_document({"manufacturer": "APC", "model": "AP7901"})

    assert text.startswith("---\n")
    assert yaml.safe_load(text) == {"manufacturer": "APC", "model": "AP7901"}


def test_output_follows_the_library_directory_layout(tmp_path):
    path = output_path({"manufacturer": "APC", "slug": "ap7901"}, tmp_path, False)

    assert path == tmp_path / "device-types" / "APC" / "ap7901.yaml"


def test_module_output_is_keyed_on_model_since_there_is_no_slug(tmp_path):
    path = output_path(
        {"manufacturer": "Juniper", "model": "EX9200-32XS"}, tmp_path, True
    )

    assert path == tmp_path / "module-types" / "Juniper" / "EX9200-32XS.yaml"


def test_path_separators_in_a_model_do_not_escape_the_output_directory(tmp_path):
    path = output_path({"manufacturer": "A/B", "model": "C/D"}, tmp_path, True)

    assert path.parent.parent == tmp_path / "module-types"
    assert path.name == "C-D.yaml"


# ---------------------------------------------------------------------------
# Pagination and fetching
# ---------------------------------------------------------------------------


def test_pagination_walks_every_page():
    rows = [{"id": n, "device_type": {"id": 1}} for n in range(600)]
    fetch = make_fetch({"dcim/interface-templates": rows})

    assert len(paginate(fetch, "dcim/interface-templates", [])) == 600


def test_a_response_without_results_is_rejected():
    def fetch(endpoint, params):
        return {"detail": "Authentication credentials were not provided."}

    with pytest.raises(ExportError, match="no 'results' list"):
        paginate(fetch, "dcim/device-types", [])


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


@pytest.fixture
def tables():
    return {
        "dcim/device-types": [DEVICE_TYPE],
        "dcim/module-types": [MODULE_TYPE],
        "dcim/power-port-templates": [POWER_PORT],
        "dcim/power-outlet-templates": [POWER_OUTLET],
    }


def test_export_writes_one_file_per_type(tmp_path, tables):
    written, _ = export(
        make_fetch(tables), tmp_path, filters=[], in_use=False, include_modules=True
    )

    assert sorted(p.name for p in written) == ["EX9200-32XS.yaml", "ap7901.yaml"]


def test_module_types_are_skipped_unless_asked_for(tmp_path, tables):
    written, _ = export(
        make_fetch(tables), tmp_path, filters=[], in_use=False, include_modules=False
    )

    assert [p.name for p in written] == ["ap7901.yaml"]


def test_in_use_keeps_only_device_types_with_devices(tmp_path, tables):
    tables["dcim/device-types"] = [
        DEVICE_TYPE,
        {**DEVICE_TYPE, "id": 9, "slug": "unused", "device_count": 0},
    ]

    written, _ = export(
        make_fetch(tables), tmp_path, filters=[], in_use=True, include_modules=False
    )

    assert [p.name for p in written] == ["ap7901.yaml"]


def test_components_are_attributed_to_the_right_parent(tmp_path):
    """Two device types in one batched response must not pool their ports."""
    second = {**DEVICE_TYPE, "id": 2, "slug": "c9200", "model": "C9200"}
    tables = {
        "dcim/device-types": [DEVICE_TYPE, second],
        "dcim/power-port-templates": [POWER_PORT],
        "dcim/interface-templates": [INTERFACE],
    }
    export(
        make_fetch(tables), tmp_path, filters=[], in_use=False, include_modules=False
    )

    ap = yaml.safe_load((tmp_path / "device-types/APC/ap7901.yaml").read_text())
    c9200 = yaml.safe_load((tmp_path / "device-types/APC/c9200.yaml").read_text())

    assert "power-ports" in ap and "interfaces" not in ap
    assert "interfaces" in c9200 and "power-ports" not in c9200


def test_exported_files_reload_as_the_library_format(tmp_path, tables):
    written, _ = export(
        make_fetch(tables), tmp_path, filters=[], in_use=False, include_modules=True
    )

    for path in written:
        document = yaml.safe_load(path.read_text())
        assert isinstance(document, dict)
        assert document.get("manufacturer") and document.get("model")
        # No API scaffolding leaks into the library format.
        for leaked in (
            "id",
            "url",
            "display",
            "created",
            "last_updated",
            "device_count",
        ):
            assert leaked not in document


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_requires_a_token(tmp_path, monkeypatch):
    monkeypatch.delenv("NETBOX_TOKEN", raising=False)

    code = main(["--url", "https://nb.example.com", "--output-dir", str(tmp_path)])

    assert code == 1


def test_cli_rejects_a_non_http_url(tmp_path):
    code = main(
        ["--url", "file:///etc/passwd", "--token", "x", "--output-dir", str(tmp_path)]
    )

    assert code == 1


def test_cli_reads_the_token_from_the_environment(tmp_path, monkeypatch):
    """A token on the command line lands in shell history; the env var does not."""
    monkeypatch.setenv("NETBOX_TOKEN", "from-env")

    args = _mod.build_parser().parse_args(
        ["--url", "https://x", "--output-dir", str(tmp_path)]
    )

    assert args.token == "from-env"
