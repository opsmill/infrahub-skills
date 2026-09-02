"""Tests for the generic-inheritance checks added alongside #112.

Two properties matter for each check: it rejects the shape its rule
forbids, and it does not reject a correct answer for its wording.
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_schemas = _load("graders/managing-schemas/lib.py", "managing_schemas_lib")
_audit = _load("graders/auditing-repo/lib.py", "auditing_repo_lib")

RULE = "yagni-duplicate-shape-not-extracted-to-generic"


def _disclose(replacement: str):
    return _audit.check_yagni_finding_replacement_mentions(
        [{"rule": RULE, "replacement": replacement}],
        RULE,
        "paired-relationship-stays-put",
    )


HOISTS_THE_RELATIONSHIP = [
    pytest.param(
        "Extract a `DcimPort` generic with the six attributes and keep the "
        "device relationships there too.",
        id="keep-there-too",
    ),
    pytest.param(
        "Move the six attributes and the device relationship onto the generic.",
        id="move-onto-the-generic",
    ),
    pytest.param(
        "Pull the shared shape up to a generic, relationships included.",
        id="relationships-included",
    ),
]


@pytest.mark.parametrize("replacement", HOISTS_THE_RELATIONSHIP)
def test_recommending_the_antipattern_fails(replacement):
    """A finding that recommends what the carve-out forbids is not a pass."""
    ok, msg = _disclose(replacement)
    assert not ok, msg


DISCLOSES_THE_COST = [
    pytest.param(
        "Extract a `DcimPort` generic with the six attributes only. Leave the "
        "device relationship on each concrete kind, because a relationship "
        "hoisted onto a generic has its peer frozen there.",
        id="frozen-peer",
    ),
    pytest.param(
        "Hoist the attributes. Do not hoist the device relationship: its peer "
        "would be frozen on the generic and no implementer could narrow it.",
        id="named-to-rule-it-out",
    ),
    pytest.param(
        "The kind-to-kind pairing is inexpressible in the schema once hoisted, "
        "so it has to live in a check.",
        id="pairing-inexpressible",
    ),
]


@pytest.mark.parametrize("replacement", DISCLOSES_THE_COST)
def test_disclosing_the_cost_passes(replacement):
    ok, msg = _disclose(replacement)
    assert ok, msg


PAIRING_NOTES_ACCEPTED = [
    pytest.param(
        "Infrahub rejects a narrowed peer on an inherited relationship, so the "
        "optical-port -> switch rule has to live in a Python check instead.",
        id="rejects-narrowed-peer",
    ),
    pytest.param(
        "The server refuses to override the inherited peer; enforce this in a "
        "check definition on the proposed change.",
        id="refuses-override",
    ),
    pytest.param(
        "# Requirement 3 is not expressible here; put it in a check.",
        id="not-expressible",
    ),
]


@pytest.mark.parametrize("text", PAIRING_NOTES_ACCEPTED)
def test_pairing_note_is_graded_on_substance_not_vocabulary(text):
    ok, msg = _schemas.CHECKS["pairing-note-present"](schema={}, raw_text=text)
    assert ok, msg


def test_a_schema_check_comment_is_not_a_pairing_note():
    ok, _ = _schemas.CHECKS["pairing-note-present"](
        schema={}, raw_text="Run `infrahubctl schema check schemas/` to validate."
    )
    assert not ok


# --- order_by ------------------------------------------------------------


def _order_by(doc: str):
    return _schemas.CHECKS["order-by-resolves-locally"](schema=yaml.safe_load(doc))


def test_the_same_target_twice_is_rejected():
    """"Each target at most once, even with opposite directions.\""""
    ok, msg = _order_by("""
version: "1.0"
generics:
  - name: Port
    namespace: Dcim
    order_by: [name__value__asc, name__value__desc]
    attributes:
      - name: name
        kind: Text
""")
    assert not ok and "twice" in msg


def test_a_node_order_by_naming_nothing_is_rejected():
    """The rule's "set order_by on each concrete kind" option had no check."""
    ok, msg = _order_by("""
version: "1.0"
nodes:
  - name: Switch
    namespace: Dcim
    order_by: [totally_bogus__value]
    attributes:
      - name: name
        kind: Text
""")
    assert not ok and "totally_bogus" in msg


def test_a_node_order_by_on_an_inherited_field_is_accepted():
    ok, msg = _order_by("""
version: "1.0"
generics:
  - name: Port
    namespace: Dcim
    attributes:
      - name: name
        kind: Text
nodes:
  - name: OpticalPort
    namespace: Dcim
    inherit_from: [DcimPort]
    order_by: [name__value__asc]
""")
    assert ok, msg


def test_a_field_inherited_from_outside_the_file_is_not_flagged():
    ok, msg = _order_by("""
version: "1.0"
nodes:
  - name: Prefix
    namespace: Net
    inherit_from: [BuiltinIPPrefix]
    order_by: [prefix__value]
""")
    assert ok, msg
