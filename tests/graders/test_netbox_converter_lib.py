"""Tests for graders/converting-netbox-device-types/lib.py.

Each check is exercised against both a compliant and a violating fixture,
so a check that silently stops asserting anything fails here.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "converting-netbox-device-types" / "lib.py"

_spec = importlib.util.spec_from_file_location("netbox_converter_graders_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["netbox_converter_graders_lib"] = _mod
_spec.loader.exec_module(_mod)

CHECKS = _mod.CHECKS
load_output_dir = _mod.load_output_dir
run_checks = _mod.run_checks


def _object_doc(kind: str, data: list[dict]) -> dict:
    """Build a well-formed Infrahub object document."""
    return {
        "apiVersion": "infrahub.app/v1",
        "kind": "Object",
        "spec": {"kind": kind, "data": data},
    }


COMPLIANT_TEMPLATE = {
    "template_name": "cisco-c9300-48p",
    "device_type": "Catalyst 9300-48P",
    "status": "active",
    "interfaces": {
        "kind": "TemplateInterfacePhysical",
        "data": [
            {"template_name": "cisco-c9300-48p__Gi1/0/1", "name": "Gi1/0/1"},
            {"template_name": "cisco-c9300-48p__Gi1/0/2", "name": "Gi1/0/2"},
        ],
    },
}

COMPLIANT_DEVICE_TYPE = {
    "name": "Catalyst 9300-48P",
    "part_number": "C9300-48P",
    "height": 1,
    "manufacturer": "Cisco",
}

REPORT = """# NetBox to Infrahub conversion coverage

- Skipped `console-ports` (1 entry) — not mapped by the profile
- Converted `interfaces` (2)
- Dropped from `interfaces`: `type`
"""


def _write_dir(tmp_path: Path, files: dict[str, object]) -> Path:
    """Materialise a fixture output directory."""
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    for name, payload in files.items():
        target = out / name
        if isinstance(payload, str):
            target.write_text(payload, encoding="utf-8")
        else:
            target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out


@pytest.fixture
def compliant(tmp_path):
    """A full, rule-compliant conversion output directory."""
    return _write_dir(
        tmp_path,
        {
            "01_manufacturers.yml": _object_doc("OrganizationManufacturer", [{"name": "Cisco"}]),
            "02_device_types.yml": _object_doc("DcimDeviceType", [COMPLIANT_DEVICE_TYPE]),
            "03_device_templates.yml": _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE]),
            "coverage-report.md": REPORT,
        },
    )


ALL_OUTPUT_CHECKS = [
    "envelope",
    "template-kind",
    "no-model-data-on-template",
    "component-kind-wrapper",
    "component-names-namespaced",
    "device-type-object",
    "load-order-numbering",
    "coverage-report",
]


def test_compliant_output_passes_every_check(compliant):
    result = run_checks(ALL_OUTPUT_CHECKS, compliant)
    assert result["score"] == 1.0, result["details"]


def test_empty_directory_fails(tmp_path):
    result = run_checks(["envelope"], tmp_path / "nothing")
    assert result["score"] == 0.0


def test_envelope_rejects_wrong_apiversion(tmp_path):
    doc = _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE])
    doc["apiVersion"] = "v1"
    out = _write_dir(tmp_path, {"03_device_templates.yml": doc})
    ok, message = CHECKS["envelope"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "apiVersion" in message


def test_envelope_rejects_non_list_data(tmp_path):
    doc = _object_doc("TemplateDcimDevice", [])
    doc["spec"]["data"] = {"template_name": "x"}
    out = _write_dir(tmp_path, {"03_device_templates.yml": doc})
    ok, _ = CHECKS["envelope"](load_output_dir(out), output_dir=out)
    assert not ok


def test_template_kind_rejects_base_node_kind(tmp_path):
    out = _write_dir(
        tmp_path,
        {"03_device_templates.yml": _object_doc("DcimDevice", [COMPLIANT_TEMPLATE])},
    )
    ok, message = CHECKS["template-kind"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "DcimDevice" in message


def test_template_kind_rejects_missing_template_name(tmp_path):
    row = {key: value for key, value in COMPLIANT_TEMPLATE.items() if key != "template_name"}
    out = _write_dir(
        tmp_path, {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [row])}
    )
    ok, message = CHECKS["template-kind"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "template_name" in message


@pytest.mark.parametrize("leaked", ["height", "part_number", "weight", "full_depth"])
def test_model_data_on_template_is_rejected(tmp_path, leaked):
    row = {**COMPLIANT_TEMPLATE, leaked: 1}
    out = _write_dir(
        tmp_path, {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [row])}
    )
    ok, message = CHECKS["no-model-data-on-template"](load_output_dir(out), output_dir=out)
    assert not ok
    assert leaked in message


def test_bare_component_list_is_rejected(tmp_path):
    row = {**COMPLIANT_TEMPLATE, "interfaces": [{"template_name": "a", "name": "a"}]}
    out = _write_dir(
        tmp_path, {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [row])}
    )
    ok, message = CHECKS["component-kind-wrapper"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "bare list" in message


def test_non_template_component_kind_is_rejected(tmp_path):
    row = {
        **COMPLIANT_TEMPLATE,
        "interfaces": {"kind": "InterfacePhysical", "data": [{"template_name": "a"}]},
    }
    out = _write_dir(
        tmp_path, {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [row])}
    )
    ok, message = CHECKS["component-kind-wrapper"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "InterfacePhysical" in message


def test_flat_component_names_are_rejected(tmp_path):
    row = {
        **COMPLIANT_TEMPLATE,
        "interfaces": {
            "kind": "TemplateInterfacePhysical",
            "data": [{"template_name": "Gi1/0/1", "name": "Gi1/0/1"}],
        },
    }
    out = _write_dir(
        tmp_path, {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [row])}
    )
    ok, message = CHECKS["component-names-namespaced"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "not namespaced" in message


def test_duplicate_component_names_are_rejected(tmp_path):
    row = {
        **COMPLIANT_TEMPLATE,
        "interfaces": {
            "kind": "TemplateInterfacePhysical",
            "data": [
                {"template_name": "cisco-c9300-48p__Gi1/0/1"},
                {"template_name": "cisco-c9300-48p__Gi1/0/1"},
            ],
        },
    }
    out = _write_dir(
        tmp_path, {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [row])}
    )
    ok, message = CHECKS["component-names-namespaced"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "Duplicate" in message


def test_device_type_without_model_data_is_rejected(tmp_path):
    out = _write_dir(
        tmp_path,
        {
            "02_device_types.yml": _object_doc(
                "DcimDeviceType", [{"name": "X", "manufacturer": "Cisco"}]
            )
        },
    )
    ok, message = CHECKS["device-type-object"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "model data" in message


def test_device_type_without_manufacturer_is_rejected(tmp_path):
    out = _write_dir(
        tmp_path,
        {"02_device_types.yml": _object_doc("DcimDeviceType", [{"name": "X", "height": 1}])},
    )
    ok, message = CHECKS["device-type-object"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "manufacturer" in message


def test_wrong_load_order_is_rejected(tmp_path):
    out = _write_dir(
        tmp_path,
        {
            "01_device_templates.yml": _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE]),
            "02_device_types.yml": _object_doc("DcimDeviceType", [COMPLIANT_DEVICE_TYPE]),
            "03_manufacturers.yml": _object_doc("OrganizationManufacturer", [{"name": "Cisco"}]),
        },
    )
    ok, message = CHECKS["load-order-numbering"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "Load order is wrong" in message


def test_unnumbered_files_are_rejected(tmp_path):
    out = _write_dir(
        tmp_path,
        {
            "manufacturers.yml": _object_doc("OrganizationManufacturer", [{"name": "Cisco"}]),
            "device_types.yml": _object_doc("DcimDeviceType", [COMPLIANT_DEVICE_TYPE]),
            "templates.yml": _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE]),
        },
    )
    ok, message = CHECKS["load-order-numbering"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "numbered" in message


def test_missing_coverage_report_is_rejected(tmp_path):
    out = _write_dir(
        tmp_path,
        {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE])},
    )
    ok, message = CHECKS["coverage-report"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "No Markdown coverage report" in message


def test_report_without_component_lists_is_rejected(tmp_path):
    out = _write_dir(
        tmp_path,
        {
            "03_device_templates.yml": _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE]),
            "coverage-report.md": "# Coverage\n\nEverything went fine.\n",
        },
    )
    ok, message = CHECKS["coverage-report"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "component lists" in message


def test_generate_template_prerequisite_detected(tmp_path):
    out = _write_dir(
        tmp_path,
        {"schema.yml": "nodes:\n  - name: Device\n    generate_template: true\n"},
    )
    ok, _ = CHECKS["generate-template-prerequisite"](load_output_dir(out), output_dir=out)
    assert ok


def test_generate_template_prerequisite_missing(tmp_path):
    out = _write_dir(
        tmp_path,
        {"03_device_templates.yml": _object_doc("TemplateDcimDevice", [COMPLIANT_TEMPLATE])},
    )
    ok, message = CHECKS["generate-template-prerequisite"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "generate_template" in message


def test_generate_template_mentioned_but_not_enabled(tmp_path):
    out = _write_dir(
        tmp_path,
        {"notes.md": "You may want generate_template: false for now.\n"},
    )
    ok, message = CHECKS["generate-template-prerequisite"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "not shown set to true" in message


def test_run_checks_reports_failed_names(tmp_path):
    out = _write_dir(
        tmp_path,
        {"03_device_templates.yml": _object_doc("DcimDevice", [COMPLIANT_TEMPLATE])},
    )
    result = run_checks(["envelope", "template-kind"], out)
    assert result["score"] == 0.5
    assert "template-kind" in result["details"]
    assert [entry["name"] for entry in result["checks"]] == ["envelope", "template-kind"]


def test_every_registered_check_is_covered_by_a_grader_script():
    grader_dir = _LIB_PATH.parent
    referenced: set[str] = set()
    for script in grader_dir.glob("check_*.py"):
        text = script.read_text(encoding="utf-8")
        referenced.update(name for name in CHECKS if f'"{name}"' in text)
    assert referenced == set(CHECKS), f"Checks with no grader script: {set(CHECKS) - referenced}"


# ---------------------------------------------------------------------------
# Fallback precedence
# ---------------------------------------------------------------------------

FALLBACK_REPORT = """# Coverage

- Shadowed: device_type `comments` lost to `description` on `description` — both were set
- Skipped `console-ports` (1 entry) — not mapped by the profile
"""


def _fallback_dir(tmp_path, device_type, children, report=FALLBACK_REPORT):
    """Build an output directory exercising the fallback checks."""
    template = {
        **COMPLIANT_TEMPLATE,
        "interfaces": {
            "kind": "TemplateInterfacePhysical",
            "data": children,
        },
    }
    return _write_dir(
        tmp_path,
        {
            "02_device_types.yml": _object_doc("DcimDeviceType", [device_type]),
            "03_device_templates.yml": _object_doc("TemplateDcimDevice", [template]),
            "coverage-report.md": report,
        },
    )


GOOD_CHILDREN = [
    {"template_name": "cisco-c9300-48p__Gi1/0/1", "name": "Gi1/0/1", "description": "Uplink"},
    {"template_name": "cisco-c9300-48p__Gi1/0/2", "name": "Gi1/0/2"},
]
GOOD_DEVICE_TYPE = {**COMPLIANT_DEVICE_TYPE, "description": "Branch access switch"}


def test_fallback_precedence_passes_on_compliant_output(tmp_path):
    out = _fallback_dir(tmp_path, GOOD_DEVICE_TYPE, GOOD_CHILDREN)
    ok, message = CHECKS["fallback-precedence"](load_output_dir(out), output_dir=out)
    assert ok, message


def test_fallback_precedence_accepts_a_url_when_the_fallback_legitimately_won(tmp_path):
    """A datasheet URL is correct output when the primary source was absent.

    Real device types often set `comments` and not `description`, so the
    shared check must not treat a URL as a precedence failure — that would
    fail thousands of correct conversions.
    """
    url_only = {**COMPLIANT_DEVICE_TYPE, "description": "[Data Sheet](https://example.com/ds.pdf)"}
    out = _fallback_dir(tmp_path, url_only, GOOD_CHILDREN)
    ok, message = CHECKS["fallback-precedence"](load_output_dir(out), output_dir=out)
    assert ok, message


def test_fallback_precedence_rejects_missing_component_descriptions(tmp_path):
    bare = [{"template_name": "cisco-c9300-48p__Gi1/0/1", "name": "Gi1/0/1"}]
    out = _fallback_dir(tmp_path, GOOD_DEVICE_TYPE, bare)
    ok, message = CHECKS["fallback-precedence"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "fallback did not" in message


def test_fallback_precedence_rejects_unreported_shadowing(tmp_path):
    out = _fallback_dir(
        tmp_path, GOOD_DEVICE_TYPE, GOOD_CHILDREN, report="# Coverage\n\nSkipped `console-ports`.\n"
    )
    ok, message = CHECKS["fallback-precedence"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "no shadowed value" in message


def test_fallback_precedence_requires_a_report(tmp_path):
    template = {
        **COMPLIANT_TEMPLATE,
        "interfaces": {"kind": "TemplateInterfacePhysical", "data": GOOD_CHILDREN},
    }
    out = _write_dir(
        tmp_path,
        {
            "02_device_types.yml": _object_doc("DcimDeviceType", [GOOD_DEVICE_TYPE]),
            "03_device_templates.yml": _object_doc("TemplateDcimDevice", [template]),
        },
    )
    ok, message = CHECKS["fallback-precedence"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "No coverage report" in message


# ---------------------------------------------------------------------------
# Two NetBox lists sharing one relationship (list-of-blocks form)
# ---------------------------------------------------------------------------

SHARED_TEMPLATE = {
    "template_name": "cisco-c9300-48p",
    "device_type": "Catalyst 9300-48P",
    "interfaces": [
        {
            "kind": "TemplateInterfacePhysical",
            "data": [{"template_name": "cisco-c9300-48p__Gi1/0/1", "name": "Gi1/0/1"}],
        },
        {
            "kind": "TemplateDcimConsoleInterface",
            "data": [{"template_name": "cisco-c9300-48p__console__con 0", "name": "con 0"}],
        },
    ],
}


def _shared_dir(tmp_path, template=SHARED_TEMPLATE):
    return _write_dir(
        tmp_path,
        {
            "01_manufacturers.yml": _object_doc("OrganizationManufacturer", [{"name": "Cisco"}]),
            "02_device_types.yml": _object_doc("DcimDeviceType", [COMPLIANT_DEVICE_TYPE]),
            "03_device_templates.yml": _object_doc("TemplateDcimDevice", [template]),
            "coverage-report.md": REPORT,
        },
    )


def test_list_of_blocks_passes_the_wrapper_check(tmp_path):
    out = _shared_dir(tmp_path)
    ok, message = CHECKS["component-kind-wrapper"](load_output_dir(out), output_dir=out)
    assert ok, message


def test_bare_child_list_is_still_rejected(tmp_path):
    """The list form must not weaken the check into accepting raw children."""
    bare = {**SHARED_TEMPLATE, "interfaces": [{"template_name": "x", "name": "Gi1/0/1"}]}
    out = _shared_dir(tmp_path, bare)
    ok, message = CHECKS["component-kind-wrapper"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "bare list" in message


def test_non_template_kind_inside_a_block_list_is_rejected(tmp_path):
    bad = {
        **SHARED_TEMPLATE,
        "interfaces": [
            {"kind": "TemplateInterfacePhysical", "data": [{"template_name": "a"}]},
            {"kind": "DcimConsoleInterface", "data": [{"template_name": "b"}]},
        ],
    }
    out = _shared_dir(tmp_path, bad)
    ok, message = CHECKS["component-kind-wrapper"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "DcimConsoleInterface" in message


def test_names_across_shared_blocks_are_checked(tmp_path):
    colliding = {
        **SHARED_TEMPLATE,
        "interfaces": [
            {
                "kind": "TemplateInterfacePhysical",
                "data": [{"template_name": "cisco-c9300-48p__dup"}],
            },
            {
                "kind": "TemplateDcimConsoleInterface",
                "data": [{"template_name": "cisco-c9300-48p__dup"}],
            },
        ],
    }
    out = _shared_dir(tmp_path, colliding)
    ok, message = CHECKS["component-names-namespaced"](load_output_dir(out), output_dir=out)
    assert not ok
    assert "Duplicate" in message


def test_shared_blocks_pass_the_full_check_set(tmp_path):
    out = _shared_dir(tmp_path)
    result = run_checks(ALL_OUTPUT_CHECKS, out)
    assert result["score"] == 1.0, result["details"]


def test_empty_list_is_rejected(tmp_path):
    out = _shared_dir(tmp_path, {**SHARED_TEMPLATE, "interfaces": []})
    ok, _ = CHECKS["component-kind-wrapper"](load_output_dir(out), output_dir=out)
    assert not ok
