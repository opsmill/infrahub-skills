"""Tests for the uniqueness-scope checks in graders/managing-schemas/lib.py.

The schemas below are the ones the eval task can actually receive: the
right answer in both of the forms the rule sanctions, and the wrong answers
that a proportional score would otherwise wave through.
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB = _REPO_ROOT / "graders" / "managing-schemas" / "lib.py"
_spec = importlib.util.spec_from_file_location("managing_schemas_lib", _LIB)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

TASK_CHECKS = [
    "schema-version",
    "uniqueness-not-on-generic",
    "uniqueness-scopes-by-relationship",
    "uniqueness-rel-mandatory",
    "uniqueness-no-optional-attr",
    "uniqueness-attr-value-suffix",
    "full-kind-references",
]

EXPLICIT = '    uniqueness_constraints:\n      - ["rack", "name__value"]'
HFID = '    human_friendly_id: ["rack", "name__value"]'
ESTATE_WIDE = '    uniqueness_constraints:\n      - ["serial__value"]'


def _schema(generic_body="", optical_body="", ethernet_body="", optional="false"):
    return yaml.safe_load(f"""
version: "1.0"
generics:
  - name: Endpoint
    namespace: Net
    attributes:
      - name: name
        kind: Text
      - name: serial
        kind: Text
{generic_body}
nodes:
  - name: Rack
    namespace: Loc
    attributes:
      - name: name
        kind: Text
  - name: OpticalEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
{optical_body}
    relationships:
      - name: rack
        peer: LocRack
        cardinality: one
        optional: {optional}
  - name: EthernetEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
{ethernet_body}
    relationships:
      - name: rack
        peer: LocRack
        cardinality: one
        optional: {optional}
""")


def _score(schema) -> float:
    passed = 0
    for name in TASK_CHECKS:
        ok, _ = _mod.CHECKS[name](schema=schema)
        passed += bool(ok)
    return passed / len(TASK_CHECKS)


def test_explicit_constraint_on_both_kinds_is_full_marks():
    assert _score(_schema(optical_body=EXPLICIT, ethernet_body=EXPLICIT)) == 1.0


def test_hfid_and_unique_true_express_the_same_move():
    """rules/uniqueness-constraints.md tells the author to move these down.

    Two schemas that load to the same constraints must not score 0 and 1.
    """
    unique_attr = (
        "    attributes:\n      - name: serial\n        kind: Text\n"
        "        unique: true"
    )
    assert _score(_schema(optical_body=HFID, ethernet_body=unique_attr)) == 1.0


def test_constraint_left_on_the_generic_fails():
    ok, msg = _mod.CHECKS["uniqueness-not-on-generic"](
        schema=_schema(
            generic_body=ESTATE_WIDE, optical_body=EXPLICIT, ethernet_body=EXPLICIT
        )
    )
    assert not ok and "NetEndpoint" in msg


def test_hfid_left_on_the_generic_fails():
    ok, msg = _mod.CHECKS["uniqueness-not-on-generic"](
        schema=_schema(
            generic_body='    human_friendly_id: ["name__value"]',
            optical_body=EXPLICIT,
            ethernet_body=EXPLICIT,
        )
    )
    assert not ok and "human_friendly_id" in msg


def test_one_implementer_left_open_fails():
    ok, _ = _mod.CHECKS["uniqueness-not-on-generic"](
        schema=_schema(optical_body=EXPLICIT)
    )
    assert not ok


def test_estate_wide_constraint_with_an_optional_parent_fails():
    """The shape that used to score 5/5 while implementing a different rule."""
    schema = _schema(
        optical_body=ESTATE_WIDE, ethernet_body=ESTATE_WIDE, optional="true"
    )
    ok, msg = _mod.CHECKS["uniqueness-scopes-by-relationship"](schema=schema)
    assert not ok and "names no" in msg
    assert _score(schema) < 1.0


def test_optional_attribute_in_a_constraint_fails():
    schema = yaml.safe_load("""
version: "1.0"
nodes:
  - name: Pdu
    namespace: Dcim
    uniqueness_constraints:
      - ["rack", "serial__value"]
    attributes:
      - name: serial
        kind: Text
        optional: true
    relationships:
      - name: rack
        peer: DcimRack
        cardinality: one
        optional: false
""")
    ok, msg = _mod.CHECKS["uniqueness-no-optional-attr"](schema=schema)
    assert not ok and "NULL" in msg


@pytest.mark.parametrize("optional", ["true", "false"])
def test_ip_namespace_carveout_survives_an_intermediate_generic(optional):
    """A kind reaching BuiltinIPPrefix through a local generic is exempt too."""
    schema = yaml.safe_load(f"""
version: "1.0"
generics:
  - name: BasePrefix
    namespace: Net
    inherit_from: [BuiltinIPPrefix]
nodes:
  - name: Prefix
    namespace: Net
    inherit_from: [NetBasePrefix]
    uniqueness_constraints:
      - ["ip_namespace", "prefix__value"]
    attributes:
      - name: prefix
        kind: Text
    relationships:
      - name: ip_namespace
        peer: BuiltinIPNamespace
        cardinality: one
        optional: {optional}
""")
    ok, msg = _mod.CHECKS["uniqueness-rel-mandatory"](schema=schema)
    assert ok, msg
