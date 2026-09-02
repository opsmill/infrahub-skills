"""Tests for the reuse and generic-membership checks in managing-schemas.

The membership task's two checks were both blind: an empty stub scored 1.0
because every keyword they look for appeared inside a `# TODO` comment or
was handed over by the prompt. These lock the discrimination in.
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "managing_schemas_lib", _REPO_ROOT / "graders" / "managing-schemas" / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SCHEMA = yaml.safe_load("""
version: "1.0"
generics:
  - name: Endpoint
    namespace: Net
    uniqueness_constraints: [["name__value"]]
    attributes:
      - name: name
        kind: Text
nodes:
  - name: OpticalEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
  - name: EthernetEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
  - name: CoherentEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
""")

STUB_TEST = '''EXPECTED = {"NetCoherentEndpoint"}
# TODO: read inherit_from properly; report added / removed kinds.
def test_stub():
    assert True
'''

PINNED_TEST = '''from pathlib import Path

import yaml

EXPECTED = {
    "NetOpticalEndpoint",
    "NetEthernetEndpoint",
    "NetCoherentEndpoint",
}


def test_endpoint_implementers_are_pinned():
    doc = yaml.safe_load(Path("schemas/endpoints.yml").read_text())
    actual = {
        f"{n['namespace']}{n['name']}"
        for n in doc.get("nodes", [])
        if "NetEndpoint" in (n.get("inherit_from") or [])
    }
    added = actual - EXPECTED
    removed = EXPECTED - actual
    assert actual == EXPECTED, f"added={sorted(added)} removed={sorted(removed)}"
'''


def _pinned(src):
    return _mod.CHECKS["generic-implementer-set-pinned"](
        schema=SCHEMA, sources={"py": src}
    )


def test_a_stub_whose_keywords_live_in_a_comment_fails():
    ok, msg = _pinned(STUB_TEST)
    assert not ok, msg


def test_a_pin_matching_the_schema_passes():
    ok, msg = _pinned(PINNED_TEST)
    assert ok, msg


def test_a_pin_that_matches_no_generic_fails():
    """EXPECTED has to be of what the schema declares, not any set at all."""
    ok, msg = _pinned(PINNED_TEST.replace('"NetCoherentEndpoint",', ""))
    assert not ok and "match no generic" in msg


def test_a_live_instance_pin_fails():
    ok, _ = _pinned(PINNED_TEST.replace("import yaml", "from infrahub_sdk import InfrahubClient"))
    assert not ok


def test_no_test_at_all_fails():
    ok, _ = _pinned("")
    assert not ok


def _consumers(text):
    return _mod.CHECKS["generic-membership-consumers-noted"](
        schema=SCHEMA, raw_text=text
    )


def test_restating_the_prompt_does_not_earn_the_check():
    ok, msg = _consumers(
        '# infrahubctl schema check passes\n'
        '# either way, so run the query below after loading.\n'
        'version: "1.0"\n'
    )
    assert not ok, msg


def test_naming_the_generic_and_two_consumer_classes_passes():
    ok, msg = _consumers(
        "# Adding NetCoherentEndpoint changes every query rooted on NetEndpoint,\n"
        "# puts the new kind under the generic's uniqueness_constraints, and adds\n"
        "# it to the capacity report that sums the generic.\n"
        'version: "1.0"\n'
    )
    assert ok, msg


# --- provenance and the Builtin premise ----------------------------------


def _provenance(text):
    return _mod.CHECKS["records-marketplace-provenance"](schema={}, raw_text=text)


PROVENANCE_ACCEPTED = [
    pytest.param(
        "# infrahubctl marketplace get opsmill/location -v 1.4.0", id="version-pin"
    ),
    pytest.param(
        "# infrahubctl marketplace get opsmill/location\n"
        "# latest published, fetched 2026-09-02",
        id="documented-default-plus-date",
    ),
    pytest.param(
        "# infrahubctl marketplace get opsmill/location\n# commit: a1b2c3d4e5f6",
        id="commit-pin",
    ),
]


@pytest.mark.parametrize("text", PROVENANCE_ACCEPTED)
def test_provenance_accepts_every_pinnable_form(text):
    ok, msg = _provenance(text)
    assert ok, msg


def test_provenance_still_requires_something_pinnable():
    ok, _ = _provenance("# infrahubctl marketplace get opsmill/location")
    assert not ok


def test_a_comment_run_ends_at_a_bare_hash_line():
    """Otherwise one `marketplace get` line vouches for the whole header."""
    runs = _mod._comment_runs(
        "# infrahubctl marketplace get opsmill/location -v 1.4.0\n"
        "#\n"
        "# Also referenced here: AcmeInventedKind\n"
        "version: \"1.0\"\n"
    )
    assert len(runs) == 2
    assert "AcmeInventedKind" not in runs[0]


def _premise(text):
    return _mod.CHECKS["corrects-builtin-core-premise"](schema={}, raw_text=text)


def test_a_correct_description_of_builtin_passes_without_transcribing_it():
    ok, msg = _premise(
        "# The Builtin namespace ships only the tag kind and the three IPAM\n"
        "# primitives; there is no location kind in Infrahub core."
    )
    assert ok, msg


def test_denying_that_a_builtin_kind_is_core_does_not_pass():
    """BuiltinTag *is* core, so that sentence denies the wrong thing."""
    ok, _ = _premise(
        "# Builtin ships BuiltinIPAddress, BuiltinIPNamespace, BuiltinIPPrefix,\n"
        "# BuiltinTag.\n"
        "# BuiltinTag is not core."
    )
    assert not ok
