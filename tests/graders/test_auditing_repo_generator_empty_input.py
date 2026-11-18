"""Tests for the finding-line-in-range check in graders/auditing-repo/lib.py (#239).

These guard the check, not the audit prose. No eval task wires the check:
an audit task for the empty-input guard could not be made to fail on the
defect: the model reaches the 1.24.0 behavior through the SDK source or
the generator skill's general cleanup rule, with or without the audit
rule (see
dev/guidelines/rule-equals-test.md § "When no task can score the rule").

The scenario the fixtures model: generators/pod_leaf.py returns early on an
empty racks list at lines 8-10, and the finding has to cite that guard. The
near-miss carries the rule and the file, bound to a different line: a
python-classes finding on pod_leaf.py raised for some other construct.
Without the line binding it would pass.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "auditing-repo"
_spec = importlib.util.spec_from_file_location(
    "auditing_repo_empty_input_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks = _mod.run_checks

CHECKS = ["finding-line-in-range:python-classes:generators/pod_leaf.py:8:10"]


def _run(tmp_path: Path, payload) -> dict:
    out = tmp_path / "output.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return run_checks(CHECKS, out)


def _finding(**kw) -> dict:
    base = {"rule": "python-classes", "severity": "CRITICAL", "file": "generators/pod_leaf.py"}
    base.update(kw)
    return base


@pytest.mark.parametrize(
    ("name", "payload", "passes"),
    [
        ("compliant", [_finding(line=8)], True),
        # Line carried in the file path and as a range, wrapped in a report.
        (
            "compliant_variant",
            {"summary": {}, "findings": [
                _finding(file="generators/pod_leaf.py:9-10"),
                {"rule": "practices-watch-dependencies", "severity": "MEDIUM",
                 "file": ".infrahub.yml", "entry": "generators/pod_leaf.py"},
            ]},
            True,
        ),
        ("violating", [], False),
        # Right rule, right file, wrong construct: line 16 is the save().
        ("violating_near_miss", [_finding(line=16)], False),
        # Fails closed: a finding that cites no line cannot be bound.
        ("no_line", [_finding()], False),
        ("other_file", [_finding(file="generators/rack_spine.py", line=8)], False),
    ],
)
def test_finding_line_in_range_fixtures(tmp_path, name, payload, passes):
    result = _run(tmp_path, payload)
    assert (result["score"] == 1.0) is passes, (name, result["details"])


def test_line_check_message_names_cited_lines():
    ok, msg = _mod.check_finding_line_in_range(
        [_finding(line="16")], "python-classes", "pod_leaf.py", 8, 10
    )
    assert not ok
    assert "[16]" in msg
