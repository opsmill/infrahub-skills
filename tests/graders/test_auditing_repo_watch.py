"""Tests for the watch-flags-entry checks in graders/auditing-repo/lib.py.

The positive check has to separate "flagged this entry" from "mentioned
it". An all-clear report that names both entries in a sentence saying they
are already correct is the failure mode: it is a plausible model output,
not a degenerate one, and it asserts the opposite of what the task
measures.
"""

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "auditing-repo" / "lib.py"
_spec = importlib.util.spec_from_file_location("auditing_repo_watch_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_watch_flags_entry = _mod.check_watch_flags_entry
check_watch_does_not_flag_entry = _mod.check_watch_does_not_flag_entry

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
