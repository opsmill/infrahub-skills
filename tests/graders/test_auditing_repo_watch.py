"""Tests for the watch-flags-entry checks in graders/auditing-repo/lib.py.

The positive check has to separate "flagged this entry" from "mentioned
it". An all-clear report that names both entries in a sentence saying they
are already correct is the failure mode: it is a plausible model output,
not a degenerate one, and it asserts the opposite of what the task
measures.
"""

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "auditing-repo" / "lib.py"
_spec = importlib.util.spec_from_file_location("auditing_repo_watch_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_watch_flags_entry = _mod.check_watch_flags_entry
check_watch_does_not_flag_entry = _mod.check_watch_does_not_flag_entry
check_watch_no_third_party_in_fix = _mod.check_watch_no_third_party_in_fix
check_yagni_finding_severity = _mod.check_yagni_finding_severity

RULE = "practices-watch-dependencies"
DEVICE_CONFIG = "transforms/device_config.py"


def test_flags_entry_named_in_the_entry_field():
    findings = [
        {
            "rule": RULE,
            "file": ".infrahub.yml",
            "entry": DEVICE_CONFIG,
            "description": "no watch key, so the commit id is folded in",
            "fix": "watch: {files: [transforms/device_config_query.py]}",
        }
    ]
    ok, _ = check_watch_flags_entry(findings, RULE, DEVICE_CONFIG)
    assert ok is True


def test_all_clear_report_naming_both_entries_in_prose_does_not_count():
    findings = [
        {
            "rule": RULE,
            "file": ".infrahub.yml",
            "severity": "MEDIUM",
            "description": (
                "Reviewed transforms/device_config.py and "
                "generators/generate_fabric.py; both declare watch "
                "correctly, so no change is needed."
            ),
        }
    ]
    ok, detail = check_watch_flags_entry(findings, RULE, DEVICE_CONFIG)
    assert ok is False
    assert "identity field" in detail


def test_negative_control_still_ignores_a_passing_mention_in_prose():
    findings = [
        {
            "rule": RULE,
            "file": ".infrahub.yml",
            "entry": DEVICE_CONFIG,
            "description": (
                "unlike interface_names, which declares files: [] correctly"
            ),
        }
    ]
    ok, _ = check_watch_does_not_flag_entry(
        findings, RULE, "transforms/interface_names.py"
    )
    assert ok is True


# -- identity: whole-field match, not substring ------------------------------


@pytest.mark.parametrize(
    "finding",
    [
        {"rule": RULE, "file": ".infrahub.yml", "name": "device_config"},
        {"rule": RULE, "file": DEVICE_CONFIG},
        {"rule": RULE, "file": ".infrahub.yml", "entry": "device_config"},
        # Seen in a live trial: section-qualified with a dot.
        {"rule": RULE, "file": ".infrahub.yml", "entry": "python_transforms.device_config"},
    ],
    ids=["name-only", "file-only", "entry-stem", "section-dotted"],
)
def test_flags_entry_named_another_way(finding):
    ok, detail = check_watch_flags_entry([finding], RULE, DEVICE_CONFIG)
    assert ok is True, detail


def test_neighbouring_entry_sharing_a_prefix_does_not_flag_it():
    # The task's own fixture registers `device_config_artifact` beside the
    # `device_config` transform. Flagging the artifact is not flagging the
    # transform.
    findings = [
        {"rule": RULE, "file": ".infrahub.yml", "entry": "device_config_artifact"}
    ]
    ok, _ = check_watch_flags_entry(findings, RULE, DEVICE_CONFIG)
    assert ok is False


def test_section_qualified_neighbour_does_not_flag_it():
    findings = [
        {
            "rule": RULE,
            "file": ".infrahub.yml",
            "entry": "artifact_definitions.device_config_artifact",
        }
    ]
    ok, _ = check_watch_flags_entry(findings, RULE, DEVICE_CONFIG)
    assert ok is False


def test_neighbouring_entry_sharing_a_prefix_is_not_an_offender():
    findings = [
        {"rule": RULE, "file": ".infrahub.yml", "entry": "interface_names_v2"}
    ]
    ok, detail = check_watch_does_not_flag_entry(
        findings, RULE, "transforms/interface_names.py"
    )
    assert ok is True, detail


def test_failure_message_names_the_entries_it_saw():
    findings = [
        {"rule": RULE, "file": ".infrahub.yml", "entry": "transforms/other.py"},
        {"rule": RULE, "file": ".infrahub.yml", "entry": "generators/else.py"},
    ]
    ok, detail = check_watch_flags_entry(findings, RULE, DEVICE_CONFIG)
    assert ok is False
    assert "transforms/other.py" in detail
    assert "generators/else.py" in detail


# -- severity: every finding, not the first ----------------------------------


@pytest.mark.parametrize(
    "severities", [["MEDIUM", "MEDIUM"], ["medium"]], ids=["two-medium", "lowercase"]
)
def test_severity_passes_when_every_finding_matches(severities):
    findings = [{"rule": RULE, "severity": s} for s in severities]
    ok, detail = check_yagni_finding_severity(findings, RULE, "MEDIUM")
    assert ok is True, detail


@pytest.mark.parametrize(
    "severities",
    [["LOW"], ["MEDIUM", "CRITICAL"]],
    ids=["single-low", "second-finding-critical"],
)
def test_severity_fails_when_any_finding_deviates(severities):
    findings = [{"rule": RULE, "severity": s} for s in severities]
    ok, _ = check_yagni_finding_severity(findings, RULE, "MEDIUM")
    assert ok is False


# -- third party in a proposed fix -------------------------------------------


def test_fix_naming_a_first_party_file_named_after_a_package_passes():
    findings = [
        {"rule": RULE, "fix": "watch: {files: [src/httpx_helpers.py, lib/]}"}
    ]
    ok, detail = check_watch_no_third_party_in_fix(findings, RULE)
    assert ok is True, detail


@pytest.mark.parametrize(
    "fix",
    ["watch: {files: [infrahub_sdk]}", "watch: {files: [INFRAHUB_SDK]}"],
    ids=["lower", "upper"],
)
def test_fix_naming_an_installed_package_fails(fix):
    ok, _ = check_watch_no_third_party_in_fix([{"rule": RULE, "fix": fix}], RULE)
    assert ok is False
