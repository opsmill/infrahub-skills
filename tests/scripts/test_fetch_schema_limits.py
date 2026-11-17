"""Tests for skills/infrahub-managing-schemas/scripts/fetch_schema_limits.py.

The script reads the string-length caps from the public JSON Schema or from
`/api/openapi.json`. Both sources name their definitions `NodeSchemaWrite`
and so on. A lookup under a name that the source does not have returns no
caps, and `--check` then validates nothing, so each lookup and the empty
table have a test here (review of #247).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = (
    _REPO_ROOT / "skills" / "infrahub-managing-schemas" / "scripts" / "fetch_schema_limits.py"
)
_spec = importlib.util.spec_from_file_location("fetch_schema_limits", _SCRIPT)
fsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fsl)

_GRADER_LIB = _REPO_ROOT / "graders" / "managing-schemas" / "lib.py"


def _string(max_length: int) -> dict:
    return {"type": "string", "maxLength": max_length}


def _nullable(max_length: int) -> dict:
    return {"anyOf": [_string(max_length), {"type": "null"}]}


# The definitions as the public JSON Schema and the OpenAPI file of Infrahub
# `stable` name them.
WRITE_DEFS = {
    "NodeSchemaWrite": {
        "properties": {"name": _string(32), "namespace": _string(64), "description": _nullable(128)}
    },
    "GenericSchemaWrite": {"properties": {"name": _string(32), "description": _nullable(128)}},
    "GenericAttributeWrite": {"properties": {"name": _string(64), "description": _nullable(128)}},
    "RelationshipSchemaWrite": {"properties": {"name": _string(64), "identifier": _nullable(128)}},
}

# The definitions as older Infrahub versions name them.
OLD_OPENAPI_DEFS = {
    "NodeSchema": WRITE_DEFS["NodeSchemaWrite"],
    "GenericSchema": WRITE_DEFS["GenericSchemaWrite"],
    "AttributeSchema-Input": WRITE_DEFS["GenericAttributeWrite"],
    "RelationshipSchema": WRITE_DEFS["RelationshipSchemaWrite"],
}

EXPECTED = {
    "NodeSchema": {"name": 32, "namespace": 64, "description": 128},
    "GenericSchema": {"name": 32, "description": 128},
    "AttributeSchema": {"name": 64, "description": 128},
    "RelationshipSchema": {"name": 64, "identifier": 128},
}


def _max_lengths(caps: dict) -> dict:
    return {name: {f: info["maxLength"] for f, info in table.items()} for name, table in caps.items()}


def test_json_schema_write_definitions() -> None:
    caps = fsl.caps_from_json_schema({"$defs": WRITE_DEFS})
    assert _max_lengths(caps) == EXPECTED
    assert fsl.names_without_caps(caps) == []


@pytest.mark.parametrize("defs", [WRITE_DEFS, OLD_OPENAPI_DEFS], ids=["write-names", "old-names"])
def test_openapi_definitions(defs: dict) -> None:
    caps = fsl.caps_from_openapi({"components": {"schemas": defs}})
    assert _max_lengths(caps) == EXPECTED
    assert fsl.names_without_caps(caps) == []


def test_missing_definition_is_reported() -> None:
    """Near-miss: three definitions found, the attribute one renamed."""
    defs = {k: v for k, v in WRITE_DEFS.items() if k != "GenericAttributeWrite"}
    defs["AttributeSchemaV2"] = WRITE_DEFS["GenericAttributeWrite"]
    caps = fsl.caps_from_json_schema({"$defs": defs})
    assert caps["AttributeSchema"] == {}
    assert fsl.names_without_caps(caps) == ["AttributeSchema"]


def test_definition_without_max_length_is_reported() -> None:
    """Near-miss: the definition is found but carries a pattern only."""
    defs = dict(WRITE_DEFS, RelationshipSchemaWrite={"properties": {"name": {"pattern": "^[a-z]+$"}}})
    caps = fsl.caps_from_json_schema({"$defs": defs})
    assert fsl.names_without_caps(caps) == ["RelationshipSchema"]


OVER_CAP = 'version: "1.0"\nnodes:\n  - name: Device\n    namespace: Dcim\n    description: "' + "x" * 400 + '"\n'
WITHIN_CAP = 'version: "1.0"\nnodes:\n  - name: Device\n    namespace: Dcim\n    description: "A device"\n'


def _main(monkeypatch: pytest.MonkeyPatch, doc: dict, argv: list[str]) -> int:
    monkeypatch.setattr(fsl, "fetch", lambda url, timeout=10.0: doc)
    return fsl.main(argv)


@pytest.mark.parametrize(
    ("source", "doc"),
    [
        ([], {"$defs": WRITE_DEFS}),
        (["--openapi", "http://infrahub.test"], {"components": {"schemas": WRITE_DEFS}}),
    ],
    ids=["json-schema", "openapi"],
)
def test_check_finds_over_cap_field(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    source: list[str],
    doc: dict,
) -> None:
    over, within = tmp_path / "over.yml", tmp_path / "within.yml"
    over.write_text(OVER_CAP)
    within.write_text(WITHIN_CAP)
    assert _main(monkeypatch, doc, [*source, "--check", str(within)]) == 0
    assert _main(monkeypatch, doc, [*source, "--check", str(over)]) == 1
    assert "DcimDevice.description: 400 chars (max 128)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("source", "doc"),
    [
        ([], {"$defs": OLD_OPENAPI_DEFS | {"AttributeSchema-Input": {}}}),
        (["--openapi", "http://infrahub.test"], {"components": {"schemas": {}}}),
    ],
    ids=["json-schema", "openapi"],
)
def test_empty_table_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    source: list[str],
    doc: dict,
) -> None:
    """An over-cap file must not pass because the caps were not found."""
    over = tmp_path / "over.yml"
    over.write_text(OVER_CAP)
    assert _main(monkeypatch, doc, [*source, "--check", str(over)]) == 3
    assert "no maxLength cap for" in capsys.readouterr().err
    assert _main(monkeypatch, doc, source) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "AttributeSchema" in captured.err


# --- the grader that runs the script ----------------------------------------


def _grader_with_script(tmp_path: Path, body: str):
    """The managing-schemas grader lib, pointed at a stand-in fetch script."""
    spec = importlib.util.spec_from_file_location("managing_schemas_lib_for_limits", _GRADER_LIB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    script = tmp_path / "fetch_schema_limits.py"
    script.write_text(body)
    mod._FETCH_SCRIPT = script
    return mod


_SCHEMA = {
    "version": "1.0",
    "nodes": [{"name": "Device", "namespace": "Dcim", "description": "x" * 400}],
}


def test_grader_fails_over_cap_description(tmp_path: Path) -> None:
    tables = {name: {f: {"maxLength": n} for f, n in t.items()} for name, t in EXPECTED.items()}
    mod = _grader_with_script(tmp_path, f"import json\nprint(json.dumps({tables!r}))\n")
    ok, msg = mod.check_string_limits(_SCHEMA)
    assert not ok and "128" in msg


@pytest.mark.parametrize(
    "body",
    [
        # The script prints a table with no caps for one schema name.
        'import json\nprint(json.dumps({"NodeSchema": {"name": {"maxLength": 32}}, '
        '"GenericSchema": {"name": {"maxLength": 32}}, "AttributeSchema": {}, '
        '"RelationshipSchema": {"name": {"maxLength": 64}}}))\n',
        # The script reports the empty table itself.
        'import sys\nprint("ERROR: no maxLength cap for AttributeSchema", file=sys.stderr)\nsys.exit(1)\n',
    ],
    ids=["empty-table", "script-error"],
)
def test_grader_reports_missing_caps_as_not_verified(tmp_path: Path, body: str) -> None:
    """The over-cap schema is not graded as within limits when no caps were read."""
    mod = _grader_with_script(tmp_path, body)
    limits, error = mod._load_schema_limits()
    assert limits is None
    assert "AttributeSchema" in error
    _, msg = mod.check_string_limits(_SCHEMA)
    assert "AttributeSchema" in msg
