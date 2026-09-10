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
NetBoxSource = _mod.NetBoxSource
as_number = _mod.as_number
field = _mod.field
build_document = _mod.build_document
carry_fields = _mod.carry_fields
export = _mod.export
is_present = _mod.is_present
main = _mod.main
missing_required = _mod.missing_required
output_path = _mod.output_path
port_mappings = _mod.port_mappings
render_document = _mod.render_document
unwrap = _mod.unwrap


# ---------------------------------------------------------------------------
# Fixtures shaped like real NetBox responses
# ---------------------------------------------------------------------------

# `url` matters: pynetbox only lazy-fetches a record that carries one, so a
# fixture without it cannot reproduce the N+1 that bare getattr caused.
MANUFACTURER = {
    "id": 11,
    "url": "http://127.0.0.1/api/dcim/manufacturers/11/",
    "name": "APC",
    "slug": "apc",
    "description": "",
}

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
    "power_port": {
        "id": 16,
        "url": "http://127.0.0.1/api/dcim/power-port-templates/16/",
        "name": "Input",
        "description": "",
    },
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


class FakeSource:
    """A Source serving canned tables, honouring the id filters.

    pynetbox itself does the pagination, so there is none to model here; what
    matters is that the exporter asks for the right things and attributes the
    answers to the right parent.
    """

    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def records(self, endpoint, **filters):
        self.calls.append((endpoint, filters))
        rows = list(self.tables.get(endpoint, []))
        for key, parent in (
            ("device_type_id", "device_type"),
            ("module_type_id", "module_type"),
        ):
            if key in filters:
                want = set(filters[key])
                rows = [r for r in rows if (r.get(parent) or {}).get("id") in want]
        for key in ("manufacturer", "slug"):
            if key in filters:
                want = set(filters[key])
                rows = [
                    r
                    for r in rows
                    if (r.get(key) if key == "slug" else (r.get("manufacturer") or {}).get("slug"))
                    in want
                ]
        return rows


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
# Reading fields from records as well as mappings
# ---------------------------------------------------------------------------


class FakeRecord:
    """Stands in for a pynetbox Record, which exposes fields as attributes."""

    def __init__(self, **values):
        self.__dict__.update(values)


def test_field_reads_mappings_and_records_alike():
    assert field({"name": "Input"}, "name") == "Input"
    assert field(FakeRecord(name="Input"), "name") == "Input"
    assert field({"a": 1}, "missing") is None
    assert field(FakeRecord(a=1), "missing") is None


def test_unwrap_handles_record_style_choices_and_relations():
    assert unwrap(FakeRecord(value="nema-5-20r", label="NEMA 5-20R")) == "nema-5-20r"
    assert unwrap(FakeRecord(id=16, name="Input")) == "Input"


def test_carry_fields_works_on_records():
    """The live path hands pynetbox records straight to the same code."""
    record = FakeRecord(
        name="Outlet 1",
        label="",
        type=FakeRecord(value="nema-5-20r", label="NEMA 5-20R"),
        power_port=FakeRecord(id=16, name="Input"),
        feed_leg=None,
        description="",
    )

    carried = carry_fields(record, _mod.COMPONENT_FIELDS["power-outlets"])

    assert carried == {"name": "Outlet 1", "type": "nema-5-20r", "power_port": "Input"}


def test_components_are_requested_with_a_batched_id_filter():
    """One call per endpoint per batch, not one per device type."""
    source = FakeSource({"dcim.device_types": [DEVICE_TYPE]})
    _mod.fetch_components(source, [1, 2, 3], is_module=False)

    interface_calls = [c for c in source.calls if c[0] == "dcim.interface_templates"]
    assert len(interface_calls) == 1
    assert interface_calls[0][1] == {"device_type_id": [1, 2, 3]}


def test_module_exports_skip_endpoints_a_module_cannot_own():
    source = FakeSource({})
    _mod.fetch_components(source, [1], is_module=True)

    assert not [c for c in source.calls if c[0] == "dcim.device_bay_templates"]


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


@pytest.fixture
def tables():
    return {
        "dcim.device_types": [DEVICE_TYPE],
        "dcim.module_types": [MODULE_TYPE],
        "dcim.power_port_templates": [POWER_PORT],
        "dcim.power_outlet_templates": [POWER_OUTLET],
    }


def test_export_writes_one_file_per_type(tmp_path, tables):
    written, _ = export(
        FakeSource(tables), tmp_path, filters={}, in_use=False, include_modules=True
    )

    assert sorted(p.name for p in written) == ["EX9200-32XS.yaml", "ap7901.yaml"]


def test_module_types_are_skipped_unless_asked_for(tmp_path, tables):
    written, _ = export(
        FakeSource(tables), tmp_path, filters={}, in_use=False, include_modules=False
    )

    assert [p.name for p in written] == ["ap7901.yaml"]


def test_in_use_keeps_only_device_types_with_devices(tmp_path, tables):
    tables["dcim.device_types"] = [
        DEVICE_TYPE,
        {**DEVICE_TYPE, "id": 9, "slug": "unused", "device_count": 0},
    ]

    written, _ = export(
        FakeSource(tables), tmp_path, filters={}, in_use=True, include_modules=False
    )

    assert [p.name for p in written] == ["ap7901.yaml"]


def test_components_are_attributed_to_the_right_parent(tmp_path):
    """Two device types in one batched response must not pool their ports."""
    second = {**DEVICE_TYPE, "id": 2, "slug": "c9200", "model": "C9200"}
    tables = {
        "dcim.device_types": [DEVICE_TYPE, second],
        "dcim.power_port_templates": [POWER_PORT],
        "dcim.interface_templates": [INTERFACE],
    }
    export(
        FakeSource(tables), tmp_path, filters={}, in_use=False, include_modules=False
    )

    ap = yaml.safe_load((tmp_path / "device-types/APC/ap7901.yaml").read_text())
    c9200 = yaml.safe_load((tmp_path / "device-types/APC/c9200.yaml").read_text())

    assert "power-ports" in ap and "interfaces" not in ap
    assert "interfaces" in c9200 and "power-ports" not in c9200


def test_exported_files_reload_as_the_library_format(tmp_path, tables):
    written, _ = export(
        FakeSource(tables), tmp_path, filters={}, in_use=False, include_modules=True
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


# ---------------------------------------------------------------------------
# The live path, against a local server speaking NetBox's REST dialect
# ---------------------------------------------------------------------------
#
# Everything above stops at the Source boundary. These exercise the real
# NetBoxSource, and so pynetbox itself: auth header, pagination, filters,
# and the record shapes the exporter then reads.


@pytest.fixture
def netbox_server():
    """Serve a minimal NetBox REST API over loopback."""
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse

    tables = {
        "/api/dcim/device-types/": [DEVICE_TYPE],
        # Reachable so a stray lazy fetch resolves rather than erroring, which
        # keeps the N+1 test measuring requests instead of failures.
        "/api/dcim/manufacturers/11/": MANUFACTURER,
        "/api/dcim/power-port-templates/": [POWER_PORT],
        "/api/dcim/power-outlet-templates/": [POWER_OUTLET],
        # 300 rows forces pynetbox to page, since NetBox caps a page at 50 here.
        "/api/dcim/interface-templates/": [
            {**INTERFACE, "id": n, "name": f"Gi1/0/{n}", "device_type": {"id": 8}}
            for n in range(300)
        ],
    }
    # Endpoints a real NetBox has but this fixture leaves empty. Without
    # these the server would 404 and the exporter would (correctly) report a
    # missing endpoint, which is a different test.
    for empty in (
        "/api/dcim/console-port-templates/",
        "/api/dcim/console-server-port-templates/",
        "/api/dcim/front-port-templates/",
        "/api/dcim/rear-port-templates/",
        "/api/dcim/module-bay-templates/",
        "/api/dcim/device-bay-templates/",
        "/api/dcim/inventory-item-templates/",
    ):
        tables[empty] = []
    seen = {"tokens": set(), "pages": 0, "paths": []}
    page_size = 50

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's interface
            seen["tokens"].add(self.headers.get("Authorization"))
            seen["paths"].append(urlparse(self.path).path)
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            rows = tables.get(parsed.path)
            if isinstance(rows, dict):  # a detail endpoint, not a list
                body = _json.dumps(rows).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if rows is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"detail":"Not found."}')
                return
            if "device_type_id" in query:
                want = {int(v) for v in query["device_type_id"]}
                rows = [r for r in rows if (r.get("device_type") or {}).get("id") in want]
            offset = int(query.get("offset", [0])[0])
            # NetBox treats limit=0 as "no client limit", capped by the server.
            requested = int(query.get("limit", [page_size])[0]) or page_size
            limit = min(requested, page_size)
            page = rows[offset : offset + limit]
            following = offset + limit
            nxt = (
                f"http://{self.headers['Host']}{parsed.path}?limit={limit}&offset={following}"
                if following < len(rows)
                else None
            )
            seen["pages"] += 1
            body = _json.dumps({"count": len(rows), "next": nxt, "previous": None,
                                "results": page}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", seen
    server.shutdown()


def test_live_path_exports_through_pynetbox(netbox_server, tmp_path):
    url, _ = netbox_server
    source = NetBoxSource(url, "secret-token")

    written, notes = export(source, tmp_path, filters={}, in_use=False, include_modules=False)

    assert [p.name for p in written] == ["ap7901.yaml"]
    document = yaml.safe_load(written[0].read_text())
    assert document["manufacturer"] == "APC"
    # The outlet's related power_port survived as a name, not a primary key.
    assert document["power-outlets"][0]["power_port"] == "Input"
    assert any("unset 'type'" in note for note in notes)


def test_live_path_sends_the_token(netbox_server, tmp_path):
    url, seen = netbox_server
    export(
        NetBoxSource(url, "secret-token"),
        tmp_path,
        filters={},
        in_use=False,
        include_modules=False,
    )

    assert "Token secret-token" in seen["tokens"]


def test_live_path_follows_pagination(netbox_server, tmp_path):
    """300 interfaces over a 50-row page cap must all arrive."""
    url, _ = netbox_server
    export(
        NetBoxSource(url, "t"), tmp_path, filters={}, in_use=False, include_modules=False
    )

    document = yaml.safe_load((tmp_path / "device-types/APC/ap7901.yaml").read_text())
    assert len(document["interfaces"]) == 300


def test_live_path_reports_an_unreachable_host(tmp_path):
    source = NetBoxSource("http://127.0.0.1:1", "t")

    with pytest.raises(ExportError) as excinfo:
        list(source.records("dcim.device_types"))

    assert "127.0.0.1:1" in str(excinfo.value)


def test_an_endpoint_this_netbox_lacks_is_reported_not_fatal(netbox_server, tmp_path):
    """Component endpoints come and go across NetBox versions."""
    url, _ = netbox_server
    source = NetBoxSource(url, "t")
    # Point one component list at an endpoint the server does not serve.
    original = _mod.DEVICE_COMPONENTS
    _mod.DEVICE_COMPONENTS = (*original, ("dcim.gone_templates", "device-bays"))
    try:
        written, notes = export(
            source, tmp_path, filters={}, in_use=False, include_modules=False
        )
    finally:
        _mod.DEVICE_COMPONENTS = original

    assert written, "the rest of the export must still complete"
    assert any("gone_templates" in note and "absent" in note for note in notes)


def test_reading_a_nested_object_does_not_trigger_a_second_request(netbox_server, tmp_path):
    """pynetbox lazily fetches unknown attributes; probing must not do that.

    Record.__getattr__ calls full_details() for anything the record does not
    already hold, which is an HTTP GET. unwrap() probes 'value' before 'name',
    so a bare getattr fired one request per nested manufacturer, power_port
    and device_type — thousands across a real catalogue, to learn nothing.
    """
    url, seen = netbox_server
    export(
        NetBoxSource(url, "t"), tmp_path, filters={}, in_use=False, include_modules=False
    )

    detail_calls = [
        path
        for path in seen["paths"]
        if path.rstrip("/").rsplit("/", 1)[-1].isdigit()  # /api/dcim/manufacturers/11/
    ]
    assert detail_calls == [], f"lazy detail fetches leaked: {detail_calls}"


def test_the_export_stays_within_one_call_per_endpoint(netbox_server, tmp_path):
    """One list call per endpoint per batch, plus pagination — nothing per object."""
    url, seen = netbox_server
    export(
        NetBoxSource(url, "t"), tmp_path, filters={}, in_use=False, include_modules=False
    )

    # 1 device-types call + 10 component endpoints + 5 extra interface pages
    # (300 rows over a 50-row cap). Anything materially above that is N+1.
    assert len(seen["paths"]) <= 20, seen["paths"]


# ---------------------------------------------------------------------------
# Filename collisions
# ---------------------------------------------------------------------------
#
# NetBox enforces (manufacturer, slug) and (manufacturer, model) uniqueness,
# but not after sanitising for the filesystem. Two legal records can want the
# same file, and the loser used to vanish while still being counted as
# written.


def test_sanitising_collision_keeps_both_records(tmp_path):
    """'EX9200 32XS' and 'EX9200-32XS' are both legal and both want one name."""
    mods = [
        {"id": 1, "manufacturer": {"name": "Juniper"}, "model": "EX9200 32XS"},
        {"id": 2, "manufacturer": {"name": "Juniper"}, "model": "EX9200-32XS"},
    ]
    source = FakeSource({"dcim.module_types": mods})

    written, notes = export(
        source, tmp_path, filters={}, in_use=False, include_modules=True
    )

    on_disk = sorted(p.name for p in tmp_path.rglob("*.yaml"))
    assert len(written) == 2
    assert on_disk == ["EX9200-32XS-2.yaml", "EX9200-32XS.yaml"]
    assert any("collided" in note for note in notes)


def test_every_claimed_file_actually_exists(tmp_path):
    """The count the script reports must match what is on disk."""
    mods = [
        {"id": n, "manufacturer": {"name": "J"}, "model": m}
        for n, m in enumerate(["A B", "A-B", "A/B", "A  B"], start=1)
    ]
    source = FakeSource({"dcim.module_types": mods})

    written, _ = export(source, tmp_path, filters={}, in_use=False, include_modules=True)

    assert len(written) == len(mods)
    assert all(p.exists() for p in written)
    assert len(set(written)) == len(written)


def test_output_path_without_a_taken_set_is_unchanged(tmp_path):
    """The 3-argument form stays stable for callers that do not track paths."""
    path = output_path({"manufacturer": "APC", "slug": "ap7901"}, tmp_path, False)

    assert path == tmp_path / "device-types" / "APC" / "ap7901.yaml"


def test_a_manufacturer_with_a_slash_stays_one_directory(tmp_path):
    taken: set = set()
    path = output_path({"manufacturer": "A/B", "slug": "x"}, tmp_path, False, taken)

    assert path.parent == tmp_path / "device-types" / "A-B"


# ---------------------------------------------------------------------------
# Failure modes found in review
# ---------------------------------------------------------------------------


def test_a_wrong_url_fails_loudly_rather_than_exporting_nothing(tmp_path):
    """pynetbox reports a bad base URL as a 404 on every endpoint.

    Treating that as "this NetBox lacks the endpoint" swallowed all twelve
    reads and exited 2 with 'No device types matched the given filters',
    pointing the user at their filters instead of their URL.
    """
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class NotFound(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(_json.dumps({"detail": "Not found."}).encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), NotFound)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        source = NetBoxSource(f"http://127.0.0.1:{server.server_port}", "t")
        with pytest.raises(ExportError) as excinfo:
            export(source, tmp_path, filters={}, in_use=False, include_modules=False)
        assert "--url" in str(excinfo.value)
    finally:
        server.shutdown()


def test_slug_is_not_sent_to_the_module_type_query(tmp_path):
    """ModuleType has no slug, and NetBox 400s on an unknown filter."""
    source = FakeSource({"dcim.device_types": [], "dcim.module_types": []})

    export(
        source,
        tmp_path,
        filters={"slug": ["ap7901"], "manufacturer": ["apc"]},
        in_use=False,
        include_modules=True,
    )

    module_call = next(f for ep, f in source.calls if ep == "dcim.module_types")
    device_call = next(f for ep, f in source.calls if ep == "dcim.device_types")
    assert "slug" not in module_call
    assert "manufacturer" in module_call  # manufacturer is valid on both
    assert "slug" in device_call


def test_notes_are_printed_even_when_nothing_was_written(tmp_path, capsys, monkeypatch):
    """An empty export is exactly when the reader needs the diagnostics."""
    monkeypatch.setattr(
        _mod, "export", lambda *a, **k: ([], ["dcim.widget_templates — endpoint absent"])
    )
    monkeypatch.setattr(_mod, "NetBoxSource", lambda *a, **k: object())

    code = main(["--url", "https://nb", "--token", "t", "--output-dir", str(tmp_path)])

    assert code == 2
    assert "endpoint absent" in capsys.readouterr().err


def test_the_configured_timeout_reaches_the_session():
    """--timeout parsed but never applied left a stalled NetBox hanging forever.

    pynetbox has no timeout setting of its own, so the session's request
    method is wrapped. This asserts the wrapper supplies the default.
    """
    source = NetBoxSource("http://127.0.0.1:9", "t", timeout=7.5)
    seen: dict = {}
    inner = source._api.http_session.request

    # Replace what the wrapper delegates to, then call the wrapper.
    source._api.http_session.__dict__["_probe"] = None
    captured = []

    def fake_send(*args, **kwargs):
        captured.append(kwargs)
        raise RuntimeError("stop before the socket")

    source._api.http_session.send = fake_send
    try:
        inner("GET", "http://127.0.0.1:9/api/")
    except RuntimeError:
        pass
    seen = captured[0] if captured else {}
    assert seen.get("timeout") == 7.5
