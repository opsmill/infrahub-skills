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
detect_input_kind = _mod.detect_input_kind
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
    """Write a NetBox device-type or profile YAML file into ``tmp_path``.

    ``sort_keys=False`` matters: component blocks are emitted in the order
    the profile declares them, so an alphabetised fixture would not reflect
    a real authored profile.
    """
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
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
    path = _write(tmp_path, "bad.yaml", {"model": "X", "slug": "x"})
    with pytest.raises(ConversionError, match="missing required NetBox device-type field"):
        parse_device_type(path)


def test_a_slugless_file_missing_fields_is_reported_as_a_module_type(tmp_path):
    """Without a slug the file reads as a module type — say so in the error."""
    path = _write(tmp_path, "bad.yaml", {"model": "X"})
    with pytest.raises(ConversionError, match="module-type field") as excinfo:
        parse_device_type(path)
    assert "read as a module type" in str(excinfo.value)


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


def test_weight_converted_to_whole_kilograms(tmp_path, profile):
    """Infrahub Number attributes are integer-backed, so no float may escape."""
    device = parse_device_type(_write(tmp_path, "ex4300.yaml", EX4300))
    conversion = convert_all([device], profile)

    weight = conversion.device_types[0]["weight"]
    assert weight == 7  # 16.1 lb -> 7.303 kg -> 7
    assert isinstance(weight, int) and not isinstance(weight, bool)


def test_fractional_kg_is_rounded_and_reported(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["weight"] == 8  # 7.59 kg -> 8
    assert any("7.59 kg converted to 8 kg" in note for note in conversion.coverage[0].notes)


def test_whole_kg_passes_through_without_a_note(tmp_path, profile):
    device = parse_device_type(_write(tmp_path, "w.yaml", dict(C9300, weight=8)))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["weight"] == 8
    assert not any("weight" in note for note in conversion.coverage[0].notes)


def test_fractional_u_height_rounds_half_up_and_is_reported(tmp_path, profile):
    """round() would give 0 for 0.5 — banker's rounding is the wrong default here."""
    payload = dict(C9300, u_height=0.5, slug="half-u")
    device = parse_device_type(_write(tmp_path, "half.yaml", payload))
    conversion = convert_all([device], profile)

    assert conversion.device_types[0]["height"] == 1
    assert any("rounded to 1" in note for note in conversion.coverage[0].notes)


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
    assert "16.1 lb converted to 7 kg" in report
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


# ---------------------------------------------------------------------------
# Two NetBox lists sharing one Infrahub relationship
# ---------------------------------------------------------------------------

#: A schema whose console-port node inherits the interface generic — as
#: infrahub-demo-dc's DcimConsoleInterface does — takes both NetBox lists on
#: the same `interfaces` Component relationship.
SHARED_RELATIONSHIP_PROFILE = {
    "version": 1,
    "name": "shared-rel",
    "manufacturer": {"kind": "OrganizationManufacturer", "name_field": "name"},
    "device_type": {
        "kind": "DcimDeviceType",
        "manufacturer_relationship": "manufacturer",
        "fields": {"model": "name"},
    },
    "template": {
        "kind": "TemplateDcimDevice",
        "template_name": "{slug}",
        "device_type_relationship": "device_type",
    },
    "components": {
        "interfaces": {
            "kind": "TemplateInterfacePhysical",
            "relationship": "interfaces",
            "template_name": "{template_name}__{name}",
            "fields": {"name": "name"},
        },
        "console-ports": {
            "kind": "TemplateDcimConsoleInterface",
            "relationship": "interfaces",  # same relationship
            "template_name": "{template_name}__console__{name}",
            "fields": {"name": "name"},
        },
    },
}

SHARED_INPUT = {
    "manufacturer": "Cisco",
    "model": "Catalyst 9300-48P",
    "slug": "cisco-c9300-48p",
    "interfaces": [{"name": f"Gi1/0/{n}"} for n in range(1, 4)],
    "console-ports": [{"name": "con 0"}, {"name": "usb"}],
}


@pytest.fixture
def shared_profile(tmp_path):
    """A profile mapping two NetBox lists onto one relationship."""
    return load_profile(_write(tmp_path, "shared.yml", SHARED_RELATIONSHIP_PROFILE))


def test_shared_relationship_keeps_both_component_lists(tmp_path, shared_profile):
    """Regression: the second mapping used to silently erase the first."""
    device = parse_device_type(_write(tmp_path, "c9300.yaml", SHARED_INPUT))
    template, _ = convert_device_type(device, shared_profile)

    blocks = template["interfaces"]
    assert isinstance(blocks, list), "two mappings on one relationship must accumulate"
    assert [b["kind"] for b in blocks] == [
        "TemplateInterfacePhysical",
        "TemplateDcimConsoleInterface",
    ]
    assert [len(b["data"]) for b in blocks] == [3, 2]


def test_shared_relationship_emits_the_loader_list_form(tmp_path, shared_profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", SHARED_INPUT))
    conversion = convert_all([device], shared_profile)
    text = render_object_file(shared_profile.template_kind, conversion.templates)
    row = yaml.safe_load(text)["spec"]["data"][0]

    # Every item must be a mapping carrying `data`, which is what the SDK's
    # MANY_OBJ_LIST_DICT format requires in order to resolve kind per item.
    assert all(isinstance(item, dict) and "data" in item for item in row["interfaces"])


def test_shared_relationship_reports_both_lists_as_converted(tmp_path, shared_profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", SHARED_INPUT))
    _, coverage = convert_device_type(device, shared_profile)

    assert coverage.converted == {"interfaces": 3, "console-ports": 2}
    assert "console-ports" not in coverage.skipped_lists


def test_shared_relationship_names_stay_unique(tmp_path, shared_profile):
    device = parse_device_type(_write(tmp_path, "c9300.yaml", SHARED_INPUT))
    template, _ = convert_device_type(device, shared_profile)

    names = [c["template_name"] for b in template["interfaces"] for c in b["data"]]
    assert len(names) == len(set(names)) == 5
    assert "cisco-c9300-48p__console__con 0" in names


def test_single_mapping_still_uses_the_plain_dict_form(tmp_path, profile):
    """The common case stays the simpler, more readable shape."""
    device = parse_device_type(_write(tmp_path, "c9300.yaml", C9300))
    template, _ = convert_device_type(device, profile)

    assert isinstance(template["interfaces"], dict)
    assert template["interfaces"]["kind"] == "TemplateInterfacePhysical"


def test_three_lists_can_share_one_relationship(tmp_path):
    payload = dict(SHARED_RELATIONSHIP_PROFILE)
    payload["components"] = dict(
        payload["components"],
        **{
            "console-server-ports": {
                "kind": "TemplateDcimConsoleServerInterface",
                "relationship": "interfaces",
                "template_name": "{template_name}__csp__{name}",
                "fields": {"name": "name"},
            }
        },
    )
    profile = load_profile(_write(tmp_path, "three.yml", payload))
    source = dict(SHARED_INPUT, **{"console-server-ports": [{"name": "csp0"}]})
    device = parse_device_type(_write(tmp_path, "c9300.yaml", source))
    template, _ = convert_device_type(device, profile)

    assert [len(b["data"]) for b in template["interfaces"]] == [3, 2, 1]


# ---------------------------------------------------------------------------
# NetBox module types
# ---------------------------------------------------------------------------

MODULE_TYPE = {
    "manufacturer": "Arista",
    "model": "AWE-5300-550-A-PS",
    "part_number": "AWE-5300-550-A-PS",
    "comments": "[Datasheet](https://example.com/psu.pdf)",
    "airflow": "front-to-rear",
    "power-ports": [{"name": "{module}", "type": "iec-60320-c14", "maximum_draw": 550}],
    "interfaces": [{"name": "Ethernet{module}/1", "type": "10gbase-x-sfpp"}],
}

MODULE_PROFILE = {
    "version": 1,
    "name": "modules",
    "manufacturer": {"kind": "OrganizationManufacturer", "name_field": "name"},
    "device_type": {
        "kind": "DcimDeviceType",
        "manufacturer_relationship": "manufacturer",
        "fields": {"model": "name"},
    },
    "template": {
        "kind": "TemplateDcimDevice",
        "template_name": "{slug}",
        "device_type_relationship": "device_type",
    },
    "components": {
        "interfaces": {
            "kind": "TemplateInterfacePhysical",
            "relationship": "interfaces",
            "template_name": "{template_name}__{name}",
            "fields": {"name": "name"},
        }
    },
    "module_type": {
        "kind": "DeviceLinecardType",
        "manufacturer_relationship": "manufacturer",
        "key": "{model}",
        "fields": {
            "model": "name",
            "part_number": "part_number",
            "description": {"target": "description", "fallback": "comments"},
        },
    },
}


def _module_profile(tmp_path, **overrides):
    """Build a profile whose module_type section can be tweaked per test."""
    payload = {**MODULE_PROFILE, "module_type": {**MODULE_PROFILE["module_type"], **overrides}}
    return load_profile(_write(tmp_path, "modules.yml", payload))


@pytest.fixture
def module_profile(tmp_path):
    return _module_profile(tmp_path)


def test_a_file_without_a_slug_is_detected_as_a_module_type():
    assert detect_input_kind(MODULE_TYPE) == "module-types"
    assert detect_input_kind(C9300) == "device-types"


def test_module_type_parses_without_a_slug(tmp_path):
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    assert module.is_module
    assert module.slug == "AWE-5300-550-A-PS"  # model stands in for the slug


def test_module_type_converts_to_a_type_object(tmp_path, module_profile):
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    conversion = convert_all([module], module_profile)

    assert conversion.module_types == [
        {
            "name": "AWE-5300-550-A-PS",
            "part_number": "AWE-5300-550-A-PS",
            "description": "[Datasheet](https://example.com/psu.pdf)",
            "manufacturer": "Arista",
        }
    ]
    assert conversion.device_types == []
    assert conversion.manufacturers == [{"name": "Arista"}]


def test_module_components_are_skipped_without_a_template(tmp_path, module_profile):
    """The stock module type has no component relationships — say so."""
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    conversion = convert_all([module], module_profile)
    coverage = conversion.coverage[0]

    assert coverage.input_kind == "module-types"
    assert coverage.skipped_lists == {"power-ports": 1, "interfaces": 1}
    assert conversion.module_templates == []


def test_module_template_carries_components_when_configured(tmp_path):
    profile = _module_profile(
        tmp_path,
        template={
            "kind": "TemplateDeviceLinecard",
            "template_name": "mod__{model}",
            "module_type_relationship": "linecard_type",
        },
        components={
            "power-ports": {
                "kind": "TemplateDcimPowerPort",
                "relationship": "power_ports",
                "template_name": "{template_name}__{name}",
                "fields": {"name": "name"},
            }
        },
    )
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    conversion = convert_all([module], profile)

    template = conversion.module_templates[0]
    assert template["template_name"] == "mod__AWE-5300-550-A-PS"
    assert template["linecard_type"] == "AWE-5300-550-A-PS"
    assert template["power_ports"]["kind"] == "TemplateDcimPowerPort"
    assert conversion.coverage[0].converted == {"power-ports": 1}


def test_module_position_token_is_preserved_and_reported(tmp_path):
    profile = _module_profile(
        tmp_path,
        template={"kind": "TemplateDeviceLinecard", "template_name": "mod__{model}"},
        components={
            "power-ports": {
                "kind": "TemplateDcimPowerPort",
                "relationship": "power_ports",
                "template_name": "{template_name}__{name}",
                "fields": {"name": "name"},
            }
        },
    )
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    conversion = convert_all([module], profile)

    child = conversion.module_templates[0]["power_ports"]["data"][0]
    assert child["name"] == "{module}"  # kept literal, not silently mangled
    assert any("{module}" in note for note in conversion.coverage[0].notes)


def test_module_position_token_is_substituted_when_configured(tmp_path):
    profile = _module_profile(
        tmp_path,
        position_placeholder="3",
        template={"kind": "TemplateDeviceLinecard", "template_name": "mod__{model}"},
        components={
            "power-ports": {
                "kind": "TemplateDcimPowerPort",
                "relationship": "power_ports",
                "template_name": "{template_name}__{name}",
                "fields": {"name": "name"},
            }
        },
    )
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    conversion = convert_all([module], profile)

    child = conversion.module_templates[0]["power_ports"]["data"][0]
    assert child["name"] == "3"
    assert not any("{module}" in note for note in conversion.coverage[0].notes)


def test_module_files_without_a_module_section_are_refused(tmp_path, profile):
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    with pytest.raises(ConversionError, match="no 'module_type' section"):
        convert_all([module], profile)


def test_module_components_without_a_template_are_refused(tmp_path):
    payload = {
        **MODULE_PROFILE,
        "module_type": {
            **MODULE_PROFILE["module_type"],
            "components": {"interfaces": {"kind": "K", "relationship": "r", "template_name": "n"}},
        },
    }
    with pytest.raises(ConversionError, match="needs 'module_type.template'"):
        load_profile(_write(tmp_path, "bad.yml", payload))


def test_a_mixed_tree_converts_both_families(tmp_path, module_profile):
    devices = [
        parse_device_type(_write(tmp_path, "c9300.yaml", C9300)),
        parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE)),
    ]
    conversion = convert_all(devices, module_profile)

    assert len(conversion.device_types) == 1
    assert len(conversion.module_types) == 1
    assert {c.input_kind for c in conversion.coverage} == {"device-types", "module-types"}
    # Manufacturers are pooled and de-duplicated across both families.
    assert [m["name"] for m in conversion.manufacturers] == ["Arista", "Cisco"]


def test_module_only_output_skips_empty_device_files(tmp_path, module_profile):
    module = parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE))
    written = write_outputs(convert_all([module], module_profile), module_profile, tmp_path / "o")

    assert [p.name for p in written] == ["01_manufacturers.yml", "04_module_types.yml"]


def test_module_report_labels_the_input_family(tmp_path, module_profile):
    devices = [
        parse_device_type(_write(tmp_path, "c9300.yaml", C9300)),
        parse_device_type(_write(tmp_path, "psu.yaml", MODULE_TYPE)),
    ]
    report = render_report(convert_all(devices, module_profile), module_profile)

    assert "Module types converted: 1" in report
    assert "| module |" in report
    assert "| device |" in report


def test_duplicate_module_names_are_rejected(tmp_path, module_profile):
    modules = [
        parse_device_type(_write(tmp_path, "a.yaml", MODULE_TYPE)),
        parse_device_type(_write(tmp_path, "b.yaml", dict(MODULE_TYPE, part_number="OTHER"))),
    ]
    with pytest.raises(ConversionError, match="module name .* already produced"):
        convert_all(modules, module_profile)


# ---------------------------------------------------------------------------
# Integer weights (Infrahub has no float attribute kind)
# ---------------------------------------------------------------------------


def _weight_profile(tmp_path, transform, target="weight"):
    payload = {
        "version": 1,
        "name": "weights",
        "manufacturer": {"kind": "OrganizationManufacturer", "name_field": "name"},
        "device_type": {
            "kind": "DcimDeviceType",
            "manufacturer_relationship": "manufacturer",
            "fields": {"model": "name", "weight": {"target": target, "transform": transform}},
        },
        "template": {
            "kind": "TemplateDcimDevice",
            "template_name": "{slug}",
            "device_type_relationship": "device_type",
        },
    }
    return load_profile(_write(tmp_path, f"{transform}.yml", payload))


def _weigh(tmp_path, profile, weight, unit="kg"):
    payload = {
        "manufacturer": "X",
        "model": "M",
        "slug": "m",
        "weight": weight,
        "weight_unit": unit,
    }
    device = parse_device_type(_write(tmp_path, "d.yaml", payload))
    conversion = convert_all([device], profile)
    return conversion.device_types[0], conversion.coverage[0]


@pytest.mark.parametrize(
    ("weight", "unit", "expected"),
    [
        (7.59, "kg", 8),
        (16.1, "lb", 7),
        (2.5, "kg", 3),  # half-up, not banker's rounding
        (3.5, "kg", 4),
        (500, "g", 1),  # 0.5 kg -> 1
        (13.4, "lb", 6),
    ],
)
def test_weight_kg_always_yields_an_integer(tmp_path, weight, unit, expected):
    profile = _weight_profile(tmp_path, "weight_kg")
    obj, _ = _weigh(tmp_path, profile, weight, unit)
    assert obj["weight"] == expected
    assert isinstance(obj["weight"], int)


def test_weight_kg_rounding_to_zero_is_called_out(tmp_path):
    """302 published device types are light enough to hit this."""
    profile = _weight_profile(tmp_path, "weight_kg")
    obj, coverage = _weigh(tmp_path, profile, 120, "g")

    assert obj["weight"] == 0
    note = " ".join(coverage.notes)
    assert "rounded to 0 kg" in note
    assert "grams attribute" in note  # points at the fix


@pytest.mark.parametrize(
    ("weight", "unit", "expected"),
    [
        (7.59, "kg", 7590),
        (1.24, "kg", 1240),
        (120, "g", 120),
        (16.1, "lb", 7303),
    ],
)
def test_weight_g_keeps_light_hardware_distinct(tmp_path, weight, unit, expected):
    profile = _weight_profile(tmp_path, "weight_g", target="weight_grams")
    obj, _ = _weigh(tmp_path, profile, weight, unit)
    assert obj["weight_grams"] == expected


def test_weight_g_does_not_round_light_hardware_to_zero(tmp_path):
    profile = _weight_profile(tmp_path, "weight_g", target="weight_grams")
    obj, coverage = _weigh(tmp_path, profile, 120, "g")

    assert obj["weight_grams"] == 120
    assert not any("rounded to 0" in note for note in coverage.notes)


def test_unknown_weight_unit_is_passed_through_and_reported(tmp_path):
    profile = _weight_profile(tmp_path, "weight_kg")
    obj, coverage = _weigh(tmp_path, profile, 5, "stone")

    assert obj["weight"] == 5
    assert any("unknown weight_unit" in note for note in coverage.notes)


def test_non_numeric_weight_is_passed_through_and_reported(tmp_path):
    profile = _weight_profile(tmp_path, "weight_kg")
    obj, coverage = _weigh(tmp_path, profile, "heavy")

    assert obj["weight"] == "heavy"
    assert any("not numeric" in note for note in coverage.notes)


@pytest.mark.parametrize(
    ("value", "expected"), [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, -1), (3.0, 3)]
)
def test_number_transform_rounds_half_away_from_zero(tmp_path, value, expected):
    payload = {
        "version": 1,
        "name": "n",
        "manufacturer": {"kind": "M", "name_field": "name"},
        "device_type": {
            "kind": "D",
            "manufacturer_relationship": "manufacturer",
            "fields": {"u_height": {"target": "height", "transform": "number"}},
        },
        "template": {
            "kind": "T",
            "template_name": "{slug}",
            "device_type_relationship": "device_type",
        },
    }
    profile = load_profile(_write(tmp_path, "n.yml", payload))
    device = parse_device_type(
        _write(
            tmp_path, "d.yaml", {"manufacturer": "X", "model": "M", "slug": "m", "u_height": value}
        )
    )
    assert convert_all([device], profile).device_types[0]["height"] == expected


def test_no_float_reaches_any_emitted_object(tmp_path, profile):
    """A float in a Number attribute would be rejected at load time."""
    devices = [
        parse_device_type(_write(tmp_path, "c9300.yaml", C9300)),
        parse_device_type(_write(tmp_path, "ex4300.yaml", EX4300)),
        parse_device_type(
            _write(tmp_path, "half.yaml", dict(C9300, slug="half", u_height=1.5, weight=0.4))
        ),
    ]
    conversion = convert_all(devices, profile)

    def floats(obj):
        for key, value in obj.items():
            if isinstance(value, float):
                yield key

    for row in conversion.device_types + conversion.templates:
        assert not list(floats(row)), f"float leaked into {row}"
