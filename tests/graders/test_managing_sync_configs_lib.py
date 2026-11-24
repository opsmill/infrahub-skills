"""Four-fixture runs for every task grader of infrahub-managing-sync-configs.

Each task has a compliant answer, a compliant variant written the way the
check's traversal is most likely to miss, an obvious violation, and a near
miss that keeps the rule's vocabulary while breaking it. The task scripts run
as skillgrade runs them, from the fixture directory, so the test covers the
script and the library together.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADERS = _REPO_ROOT / "graders" / "managing-sync-configs"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "managing-sync-configs"

TASKS = {
    "identifiers-hfid": "check_identifiers_hfid.py",
}
CASES = [
    (task, fixture)
    for task in TASKS
    for fixture in ("pass", "pass-variant", "fail", "fail-nearmiss")
]


def _load_lib():
    spec = importlib.util.spec_from_file_location(
        "managing_sync_configs_lib", _GRADERS / "lib.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lib = _load_lib()


def _score(task: str, fixture: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(_GRADERS / TASKS[task])],
        cwd=_FIXTURES / task / fixture,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize(("task", "fixture"), CASES)
def test_fixture_scores(task: str, fixture: str) -> None:
    result = _score(task, fixture)
    if fixture.startswith("pass"):
        assert result["score"] == 1.0, result["details"]
    else:
        assert result["score"] < 1.0, (
            f"{task}/{fixture} passed: the check does not discriminate"
        )


def test_identifiers_duplicate_mapping_does_not_hide_a_missing_kind() -> None:
    schema = {
        "nodes": [
            {
                "namespace": "Location",
                "name": "Site",
                "human_friendly_id": ["name__value"],
            },
            {
                "namespace": "Network",
                "name": "Device",
                "human_friendly_id": ["name__value"],
            },
        ]
    }
    config = {
        "schema_mapping": [
            {"name": "LocationSite", "identifiers": ["name"]},
            {"name": "LocationSite", "identifiers": ["name"]},
        ]
    }
    ok, details = lib.check_identifiers_match_hfid({"config": config, "schema": schema})
    assert not ok
    assert "NetworkDevice" in details


def test_identifiers_hfid_inherited_from_first_generic_that_declares_one() -> None:
    hfids = lib.schema_hfids(
        lib.yaml.safe_load((_GRADERS / "data" / "netbox_schema.yml").read_text())
    )
    assert hfids == {"LocationSite": ["name"], "NetworkDevice": ["name", "location"]}


_PASS = _FIXTURES / "identifiers-hfid" / "pass" / "config.yml"
_SCHEMA = lib.yaml.safe_load((_GRADERS / "data" / "netbox_schema.yml").read_text())


def _checks(config: dict) -> dict[str, bool]:
    ctx = {"config": config, "schema": _SCHEMA}
    return {name: fn(ctx)[0] for name, fn in lib.CHECKS.items()}


def _device(config: dict) -> dict:
    return next(m for m in config["schema_mapping"] if m["name"] == "NetworkDevice")


def test_nearmiss_fails_only_on_the_unmapped_identifier() -> None:
    config, _ = lib.load_yaml_file(
        _FIXTURES / "identifiers-hfid" / "fail-nearmiss" / "config.yml"
    )
    assert _checks(config) == {
        "identifiers-match-hfid": False,
        "stable-id-is-a-field": True,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d.pop("fields"), id="no fields at all"),
        pytest.param(
            lambda d: d["identifiers"].append("name"), id="duplicate identifier"
        ),
    ],
)
def test_identifiers_must_be_unique_and_mapped(mutate) -> None:
    config, _ = lib.load_yaml_file(_PASS)
    mutate(_device(config))
    assert _checks(config)["identifiers-match-hfid"] is False


def test_stable_id_check_fails_when_netbox_id_is_dropped_or_used_as_key() -> None:
    config, _ = lib.load_yaml_file(_PASS)
    site = next(m for m in config["schema_mapping"] if m["name"] == "LocationSite")
    site["fields"] = [f for f in site["fields"] if f["name"] != "netbox_id"]
    assert _checks(config)["stable-id-is-a-field"] is False

    config, _ = lib.load_yaml_file(_PASS)
    _device(config)["identifiers"].append("netbox_id")
    assert _checks(config)["stable-id-is-a-field"] is False
