"""Tests for the NetBox device-type to Infrahub object-template converter.

Covers mapping-profile validation, value transforms, template naming,
component nesting, coverage reporting, and the CLI exit codes.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# The converter ships inside a skill directory whose name is not a valid
# Python package name, so load it by file path. It must be registered in
# sys.modules before exec_module, or its dataclasses cannot resolve their
# own module namespace.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL_DIR = _REPO_ROOT / "skills" / "infrahub-converting-netbox-device-types"
_SCRIPT_PATH = _SKILL_DIR / "scripts" / "netbox_to_infrahub_templates.py"
_DEFAULT_PROFILE = _SKILL_DIR / "scripts" / "mappings" / "schema-library.yml"

_spec = importlib.util.spec_from_file_location("netbox_to_infrahub_templates", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["netbox_to_infrahub_templates"] = _mod
_spec.loader.exec_module(_mod)

ConversionError = _mod.ConversionError
convert_all = _mod.convert_all
convert_device_type = _mod.convert_device_type
format_fields = _mod.format_fields
iter_input_files = _mod.iter_input_files
load_profile = _mod.load_profile
main = _mod.main
parse_device_type = _mod.parse_device_type
render_object_file = _mod.render_object_file
render_report = _mod.render_report
write_outputs = _mod.write_outputs


C9300 = {
    "manufacturer": "Cisco",
    "model": "Catalyst 9300-48P",
    "slug": "cisco-c9300-48p",
    "part_number": "C9300-48P",
    "u_height": 1,
    "is_full_depth": True,
    "weight": 7.59,
    "weight_unit": "kg",
    "airflow": "front-to-rear",
    "console-ports": [{"name": "con 0", "type": "rj-45"}],
    "interfaces": [
        {"name": "GigabitEthernet1/0/1", "type": "1000base-t", "poe_mode": "pse"},
        {"name": "mgmt0", "type": "1000base-t", "mgmt_only": True},
    ],
}

EX4300 = {
    "manufacturer": "Juniper",
    "model": "EX4300-48T",
    "slug": "juniper-ex4300-48t",
    "u_height": 1,
    "weight": 16.1,
    "weight_unit": "lb",
    "interfaces": [{"name": "ge-0/0/0", "type": "1000base-t"}],
}


@pytest.fixture
def profile():
    """The shipped schema-library mapping profile."""
    return load_profile(_DEFAULT_PROFILE)


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    """Write a NetBox device-type YAML file into ``tmp_path``."""
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Mapping profile
# ---------------------------------------------------------------------------


def test_default_profile_loads(profile):
    assert profile.name == "schema-library"
    assert profile.template_kind == "TemplateDcimDevice"
    assert profile.device_type_kind == "DcimDeviceType"
    assert profile.mapped_lists == {"interfaces"}


def test_profile_rejects_missing_required_key(tmp_path):
    payload = {
        "manufacturer": {"kind": "M"},  # no name_field
        "device_type": {"kind": "D", "manufacturer_relationship": "manufacturer"},
        "template": {
            "kind": "T",
            "template_name": "{slug}",
            "device_type_relationship": "device_type",
        },
    }
    path = _write(tmp_path, "bad.yml", payload)
    with pytest.raises(ConversionError, match="missing required key 'name_field'"):
        load_profile(path)


def test_profile_rejects_missing_section(tmp_path):
    path = _write(tmp_path, "bad.yml", {"manufacturer": {"kind": "X", "name_field": "name"}})
    with pytest.raises(ConversionError, match="'device_type' must be a mapping"):
        load_profile(path)


def test_profile_rejects_unknown_component_list(tmp_path):
    payload = {
        "manufacturer": {"kind": "M", "name_field": "name"},
        "device_type": {"kind": "D", "manufacturer_relationship": "manufacturer"},
        "template": {
            "kind": "T",
            "template_name": "{slug}",
            "device_type_relationship": "device_type",
        },
        "components": {"widgets": {"kind": "K", "relationship": "r", "template_name": "n"}},
    }
    path = _write(tmp_path, "bad.yml", payload)
    with pytest.raises(ConversionError, match="not a NetBox component list"):
        load_profile(path)


def test_profile_rejects_unknown_transform(tmp_path):
    payload = {
        "manufacturer": {"kind": "M", "name_field": "name"},
        "device_type": {
            "kind": "D",
            "manufacturer_relationship": "manufacturer",
            "fields": {"u_height": {"target": "height", "transform": "furlongs"}},
        },
        "template": {
            "kind": "T",
            "template_name": "{slug}",
            "device_type_relationship": "device_type",
        },
    }
    path = _write(tmp_path, "bad.yml", payload)
    with pytest.raises(ConversionError, match="transform"):
        load_profile(path)


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def test_iter_input_files_walks_directories(tmp_path):
    (tmp_path / "vendor").mkdir()
    _write(tmp_path / "vendor", "a.yaml", C9300)
    _write(tmp_path / "vendor", "b.yml", EX4300)
    (tmp_path / "vendor" / "README.md").write_text("ignored", encoding="utf-8")

    found = iter_input_files([str(tmp_path)])

    assert [p.name for p in found] == ["a.yaml", "b.yml"]


def test_iter_input_files_rejects_missing_path():
    with pytest.raises(ConversionError, match="does not exist"):
        iter_input_files(["/nonexistent/path.yaml"])


def test_parse_device_type_requires_netbox_fields(tmp_path):
    path = _write(tmp_path, "bad.yaml", {"model": "X"})
    with pytest.raises(ConversionError, match="missing required NetBox field"):
        parse_device_type(path)


def test_parse_device_type_rejects_non_mapping(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ConversionError, match="expected a YAML mapping"):
        parse_device_type(path)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def test_template_carries_name_and_device_type(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    template, _ = convert_device_type(device, profile)

    assert template["template_name"] == "cisco-c9300-48p"
    assert template["device_type"] == "Catalyst 9300-48P"
    # template_name must be the first key so the emitted YAML leads with it.
    assert next(iter(template)) == "template_name"


def test_components_nest_with_kind_wrapper(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    template, _ = convert_device_type(device, profile)

    interfaces = template["interfaces"]
    assert interfaces["kind"] == "TemplateInterfacePhysical"
    assert [child["name"] for child in interfaces["data"]] == [
        "GigabitEthernet1/0/1",
        "mgmt0",
    ]


def test_component_template_names_are_namespaced_by_parent(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    template, _ = convert_device_type(device, profile)

    names = [child["template_name"] for child in template["interfaces"]["data"]]
    assert names == [
        "cisco-c9300-48p__GigabitEthernet1/0/1",
        "cisco-c9300-48p__mgmt0",
    ]


def test_derived_field_sets_management_role(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    template, _ = convert_device_type(device, profile)

    children = {child["name"]: child for child in template["interfaces"]["data"]}
    assert children["mgmt0"]["role"] == "management"
    assert "role" not in children["GigabitEthernet1/0/1"]


def test_weight_converted_to_kilograms(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "ex4300.yaml", EX4300))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["weight"] == pytest.approx(7.303)


def test_weight_in_kg_passes_through_without_a_note(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["weight"] == pytest.approx(7.59)
    assert not any("weight" in note for note in conversion.coverage[0].notes)


def test_fractional_u_height_is_reported(tmp_path, profile):
    payload = dict(C9300, u_height=0.5, slug="half-u")
    device = parse_device_type(_write(tmp_path, "half.yaml", payload))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["height"] == pytest.approx(0.5)
    assert any("non-integer" in note for note in conversion.coverage[0].notes)


def test_manufacturers_are_deduplicated_and_sorted(tmp_path, profile):
    devices = [
        parse_device_type(_write(tmp_path, "ex4300.yaml", EX4300)),
        parse_device_type(_write(tmp_path, "c9300.yaml", C9300)),
        parse_device_type(_write(tmp_path, "c9300b.yaml", dict(C9300, slug="cisco-b"))),
    ]
    conversion = convert_all(devices, profile)

    assert conversion.manufacturers == [{"name": "Cisco"}, {"name": "Juniper"}]


def test_duplicate_template_names_are_rejected(tmp_path, profile):
    devices = [
        parse_device_type(_write(tmp_path, "a.yaml", C9300)),
        parse_device_type(_write(tmp_path, "b.yaml", dict(C9300, model="Other"))),
    ]
    with pytest.raises(ConversionError, match="must be unique"):
        convert_all(devices, profile)


def test_unknown_template_name_field_is_rejected(tmp_path, profile):
    broken = _mod.Profile(**{**profile.__dict__, "template_name_format": "{does_not_exist}"})
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    with pytest.raises(ConversionError, match="unknown field"):
        convert_device_type(device, broken)


# ---------------------------------------------------------------------------
# Coverage reporting
# ---------------------------------------------------------------------------


def test_unmapped_component_lists_are_reported(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    _, coverage = convert_device_type(device, profile)

    assert coverage.skipped_lists == {"console-ports": 1}
    assert coverage.converted == {"interfaces": 1 + 1}
    assert not coverage.is_lossless


def test_unmapped_fields_are_reported(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    conversion = convert_all([device], profile)
    coverage = conversion.coverage[0]

    assert "airflow" in coverage.dropped_fields["device_type"]
    assert set(coverage.dropped_fields["interfaces"]) == {"type", "poe_mode"}


def test_consumed_fields_are_not_reported_as_dropped(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    conversion = convert_all([device], profile)
    dropped = conversion.coverage[0].dropped_fields

    # slug drives template_name, weight_unit drives the kg conversion, and
    # mgmt_only drives the derived role — none of them are lost.
    assert "slug" not in dropped["device_type"]
    assert "weight_unit" not in dropped["device_type"]
    assert "mgmt_only" not in dropped["interfaces"]


def test_report_lists_every_skip_and_coercion(tmp_path, profile):
    devices = [
        parse_device_type(_write(tmp_path, "c9300.yaml", C9300)),
        parse_device_type(_write(tmp_path, "ex4300.yaml", EX4300)),
    ]
    report = render_report(convert_all(devices, profile), profile)

    assert "console-ports" in report
    assert "16.1 lb converted to 7.303 kg" in report
    assert "`cisco-c9300-48p`" in report


def test_report_states_lossless_when_nothing_is_dropped(tmp_path, profile):
    minimal = {
        "manufacturer": "Cisco",
        "model": "Tiny",
        "slug": "cisco-tiny",
        "interfaces": [{"name": "eth0"}],
    }
    device = parse_device_type(_write(tmp_path, "tiny.yaml", minimal))
    report = render_report(convert_all([device], profile), profile)

    assert "Every field of every input mapped onto the target schema." in report


def test_format_fields_extracts_referenced_names():
    assert format_fields("{template_name}__{name}") == {"template_name", "name"}
    assert format_fields("static") == set()


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------


def test_render_object_file_emits_the_infrahub_envelope():
    text = render_object_file("DcimDeviceType", [{"name": "X"}])
    doc = yaml.safe_load(text)

    assert text.startswith("---\n")
    assert doc["apiVersion"] == "infrahub.app/v1"
    assert doc["kind"] == "Object"
    assert doc["spec"]["kind"] == "DcimDeviceType"
    assert doc["spec"]["data"] == [{"name": "X"}]


def test_write_outputs_uses_load_order_filenames(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    written = write_outputs(convert_all([device], profile), profile, tmp_path / "out")

    assert [p.name for p in written] == [
        "01_manufacturers.yml",
        "02_device_types.yml",
        "03_device_templates.yml",
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_converts_a_directory(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    _write(source, "c9300.yaml", C9300)
    out = tmp_path / "out"

    code = main(
        [
            str(source),
            "--mapping",
            str(_DEFAULT_PROFILE),
            "--output-dir",
            str(out),
            "--report",
            str(tmp_path / "report.md"),
        ]
    )

    assert code == 0
    assert (out / "03_device_templates.yml").exists()
    assert "console-ports" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_cli_returns_2_when_nothing_matches(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    code = main(
        [
            str(empty),
            "--mapping",
            str(_DEFAULT_PROFILE),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 2


def test_cli_returns_1_on_a_bad_profile(tmp_path):
    bad = _write(tmp_path, "bad-profile.yml", {"manufacturer": {}})
    _write(tmp_path, "c9300.yaml", C9300)

    code = main(
        [
            str(tmp_path / "c9300.yaml"),
            "--mapping",
            str(bad),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 1


def test_cli_writes_report_to_stdout(tmp_path, capsys):
    _write(tmp_path, "c9300.yaml", C9300)

    code = main(
        [
            str(tmp_path / "c9300.yaml"),
            "--mapping",
            str(_DEFAULT_PROFILE),
            "--output-dir",
            str(tmp_path / "out"),
            "--report",
            "-",
        ]
    )

    assert code == 0
    assert "NetBox to Infrahub conversion coverage" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Fallback sources
# ---------------------------------------------------------------------------

BOTH_TEXT = {
    "manufacturer": "Cisco",
    "model": "Catalyst Test",
    "slug": "cisco-test",
    "u_height": 1,
    "description": "Access switch for branch sites",
    "comments": "[Datasheet](https://example.com/ds.pdf)",
    "interfaces": [
        {"name": "Gi1/0/1", "label": "Uplink A", "description": "Primary uplink"},
        {"name": "Gi1/0/2", "label": "Uplink B"},
        {"name": "Gi1/0/3", "description": "Spare port"},
        {"name": "Gi1/0/4"},
    ],
}


def test_primary_source_wins_over_fallback(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "both.yaml", BOTH_TEXT))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["description"] == "Access switch for branch sites"


def test_fallback_fills_in_when_primary_absent(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "both.yaml", BOTH_TEXT))
    template, _ = convert_device_type(device, profile)
    children = {c["name"]: c for c in template["interfaces"]["data"]}

    assert children["Gi1/0/1"]["description"] == "Primary uplink"  # primary wins
    assert children["Gi1/0/2"]["description"] == "Uplink B"  # fallback fills in
    assert children["Gi1/0/3"]["description"] == "Spare port"  # only primary
    assert "description" not in children["Gi1/0/4"]  # neither present


def test_shadowed_values_are_recorded(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "both.yaml", BOTH_TEXT))
    conversion = convert_all([device], profile)
    shadowed = conversion.coverage[0].shadowed

    assert any("device_type `comments` lost to `description`" in s for s in shadowed)
    assert any("interfaces `label` lost to `description`" in s for s in shadowed)
    assert not conversion.coverage[0].is_lossless


def test_shadowing_appears_in_the_report(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "both.yaml", BOTH_TEXT))
    report = render_report(convert_all([device], profile), profile)

    assert "Shadowed:" in report
    assert "`comments` lost to `description`" in report


def test_fallback_sources_are_not_reported_as_dropped(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "both.yaml", BOTH_TEXT))
    conversion = convert_all([device], profile)
    dropped = conversion.coverage[0].dropped_fields

    assert "comments" not in dropped.get("device_type", [])
    assert "label" not in dropped.get("interfaces", [])


def test_repeated_report_lines_are_collapsed_with_a_count(tmp_path, profile):
    payload = dict(
        BOTH_TEXT,
        interfaces=[
            {"name": f"Gi1/0/{n}", "label": f"L{n}", "description": f"D{n}"} for n in range(1, 9)
        ],
    )
    device = parse_device_type(_write(tmp_path, "many.yaml", payload))
    report = render_report(convert_all([device], profile), profile)

    assert "(8 entries)" in report
    assert report.count("interfaces `label` lost to") == 1


def test_blank_primary_falls_through_to_fallback(tmp_path, profile):
    payload = dict(BOTH_TEXT, description="   ")
    device = parse_device_type(_write(tmp_path, "blank.yaml", payload))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["description"] == BOTH_TEXT["comments"]
    # A blank primary is not a competing value, so nothing is shadowed at the
    # device-type level (the interfaces still shadow — they are unchanged).
    assert not any("device_type" in s for s in conversion.coverage[0].shadowed)


def _profile_with_fields(tmp_path, fields):
    payload = {
        "manufacturer": {"kind": "M", "name_field": "name"},
        "device_type": {
            "kind": "D",
            "manufacturer_relationship": "manufacturer",
            "fields": fields,
        },
        "template": {
            "kind": "T",
            "template_name": "{slug}",
            "device_type_relationship": "device_type",
        },
    }
    return _write(tmp_path, "profile.yml", payload)


def test_undeclared_target_collision_is_rejected(tmp_path):
    path = _profile_with_fields(tmp_path, {"description": "description", "comments": "description"})
    with pytest.raises(ConversionError, match="declare one as the other's 'fallback'"):
        load_profile(path)


def test_fallback_accepts_an_ordered_list(tmp_path):
    path = _profile_with_fields(
        tmp_path, {"description": {"target": "description", "fallback": ["comments", "model"]}}
    )
    mapping = load_profile(path).device_type_fields[0]

    assert mapping.sources == ("description", "comments", "model")


def test_fallback_rejects_its_own_source(tmp_path):
    path = _profile_with_fields(
        tmp_path, {"description": {"target": "description", "fallback": "description"}}
    )
    with pytest.raises(ConversionError, match="lists its own source"):
        load_profile(path)


def test_fallback_rejects_repeated_names(tmp_path):
    path = _profile_with_fields(
        tmp_path, {"description": {"target": "description", "fallback": ["comments", "comments"]}}
    )
    with pytest.raises(ConversionError, match="repeats a field name"):
        load_profile(path)


def test_fallback_rejects_a_non_string_entry(tmp_path):
    path = _profile_with_fields(
        tmp_path, {"description": {"target": "description", "fallback": [123]}}
    )
    with pytest.raises(ConversionError, match="must be a field name or a list"):
        load_profile(path)


# ---------------------------------------------------------------------------
# Gap guidance in the coverage report
# ---------------------------------------------------------------------------


def test_report_explains_why_component_lists_were_skipped(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    report = render_report(convert_all([device], profile), profile)

    assert "## Closing these gaps" in report
    assert "Skipped component lists" in report
    assert "`Component`/`Parent` relationship pair" in report
    assert "https://docs.infrahub.app/schema/relationships" in report


def test_report_explains_dropped_fields_and_links_the_guide(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    report = render_report(convert_all([device], profile), profile)

    assert "Dropped fields" in report
    assert "`interfaces.type`" in report
    assert "https://docs.infrahub.app/schema/nodes-and-attributes" in report
    assert "extending-your-schema.md" in report
    assert "https://docs.infrahub.app/schema/extensions" in report


def test_report_explains_shadowed_values(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "both.yaml", BOTH_TEXT))
    report = render_report(convert_all([device], profile), profile)

    assert "Shadowed values" in report
    assert "Give the loser its own attribute" in report


def test_gap_guidance_says_closing_is_optional(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    report = render_report(convert_all([device], profile), profile)

    assert "Closing a gap is optional" in report


def test_gap_guidance_is_absent_when_nothing_was_lost(tmp_path, profile):
    minimal = {
        "manufacturer": "Cisco",
        "model": "Tiny",
        "slug": "cisco-tiny",
        "interfaces": [{"name": "eth0"}],
    }
    device = parse_device_type(_write(tmp_path, "tiny.yaml", minimal))
    report = render_report(convert_all([device], profile), profile)

    assert "## Closing these gaps" not in report
    assert "Every field of every input mapped onto the target schema." in report


def test_dropped_field_list_is_truncated_with_a_count(tmp_path, profile):
    noisy = dict(
        C9300,
        interfaces=[
            {
                "name": "Gi1/0/1",
                "type": "1000base-t",
                "poe_mode": "pse",
                "poe_type": "type2",
                "mtu": 9000,
                "speed": 1000,
                "duplex": "full",
                "mode": "access",
                "enabled": True,
                "mark_connected": True,
            }
        ],
    )
    device = parse_device_type(_write(tmp_path, "noisy.yaml", noisy))
    report = render_report(convert_all([device], profile), profile)

    assert "more)" in report
