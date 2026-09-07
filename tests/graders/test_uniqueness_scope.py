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


def test_hfid_and_the_explicit_key_express_the_same_move():
    """rules/uniqueness-constraints.md sanctions both forms.

    A human_friendly_id compiles into the same uniqueness_constraints on the
    layer that declares it, so two schemas that load to the same constraints
    must not score 0 and 1.
    """
    assert _score(_schema(optical_body=HFID, ethernet_body=EXPLICIT)) == 1.0
    assert _score(_schema(optical_body=HFID, ethernet_body=HFID)) == 1.0


def test_unique_true_cannot_express_this_rule():
    """`unique: true` is a form of uniqueness, not a form of *this* rule.

    It compiles to `[["serial__value"]]` on the declaring kind — one
    attribute, estate-wide, no relationship. It satisfies
    `uniqueness-not-on-generic`, whose question is only whether the
    implementer declares uniqueness of its own, and must not satisfy the
    scope check, whose question is whether the name is scoped by the rack.
    """
    unique_attr = (
        "    attributes:\n      - name: serial\n        kind: Text\n"
        "        unique: true"
    )
    schema = _schema(optical_body=HFID, ethernet_body=unique_attr)
    assert _mod.CHECKS["uniqueness-not-on-generic"](schema=schema)[0]
    ok, msg = _mod.CHECKS["uniqueness-scopes-by-relationship"](schema=schema)
    assert not ok and "NetEthernetEndpoint" in msg
    assert _score(schema) < 1.0


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
    assert not ok and "pairs no relationship with the endpoint name" in msg
    assert _score(schema) < 1.0


WRONG_PAIR = '    uniqueness_constraints:\n      - ["rack", "serial__value"]'


def test_a_relationship_paired_with_the_wrong_attribute_fails():
    """A mixed pair is not the rule; the requested pair is.

    `[rack, serial__value]` on both kinds names a relationship and an
    attribute, so an any-relationship-plus-any-attribute assertion passes it
    while neither kind enforces name uniqueness within the rack.
    """
    schema = _schema(optical_body=WRONG_PAIR, ethernet_body=WRONG_PAIR)
    ok, msg = _mod.CHECKS["uniqueness-scopes-by-relationship"](schema=schema)
    assert not ok
    assert "NetOpticalEndpoint" in msg and "NetEthernetEndpoint" in msg


def test_one_implementer_scoped_and_its_sibling_open_fails():
    ok, msg = _mod.CHECKS["uniqueness-scopes-by-relationship"](
        schema=_schema(optical_body=EXPLICIT)
    )
    assert not ok and "NetEthernetEndpoint" in msg


def test_an_extra_constraint_alongside_the_requested_one_is_fine():
    both = (
        "    uniqueness_constraints:\n"
        '      - ["serial__value"]\n'
        '      - ["rack", "name__value"]'
    )
    ok, msg = _mod.CHECKS["uniqueness-scopes-by-relationship"](
        schema=_schema(optical_body=both, ethernet_body=EXPLICIT)
    )
    assert ok, msg


def test_the_rack_nodes_own_uniqueness_is_not_asked_to_scope():
    """`LocRack` implements nothing and has no relationship to scope by.

    Its own `[["name__value"]]` is the correct thing for a container to
    declare, and reading it as a failed scoping made the right answer fail.
    """
    schema = _schema(optical_body=EXPLICIT, ethernet_body=EXPLICIT)
    for node in schema["nodes"]:
        if node["name"] == "Rack":
            node["uniqueness_constraints"] = [["name__value"]]
    ok, msg = _mod.CHECKS["uniqueness-scopes-by-relationship"](schema=schema)
    assert ok, msg
    assert _score(schema) == 1.0


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
