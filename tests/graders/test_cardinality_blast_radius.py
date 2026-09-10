"""Tests for the cardinality blast-radius checks.

The point of the rule is *which side actually caps*. Two of these tests
exist because the grader could not tell the precise fix from the blunt one,
which made that point the one thing the eval could not see.
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADERS = _REPO_ROOT / "graders" / "managing-schemas"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_schemas = _load(_GRADERS / "lib.py", "managing_schemas_lib")
_sharing = _load(_GRADERS / "check_cardinality_sharing.py", "check_cardinality_sharing")
_audit = _load(_REPO_ROOT / "graders" / "auditing-repo" / "lib.py", "auditing_repo_lib")


def _schema(service_cardinality: str, wavelength_cardinality: str) -> dict:
    return yaml.safe_load(f"""
version: "1.0"
nodes:
  - name: Service
    namespace: Net
    attributes:
      - name: name
        kind: Text
    relationships:
      - name: wavelength
        peer: NetWavelength
        cardinality: {service_cardinality}
        optional: false
        identifier: service__wavelength
  - name: Wavelength
    namespace: Net
    attributes:
      - name: name
        kind: Text
    relationships:
      - name: service
        peer: NetService
        cardinality: {wavelength_cardinality}
        optional: true
        identifier: service__wavelength
""")


def test_widening_the_side_that_caps_passes():
    ok, msg = _sharing.check_shared_side_widened(_schema("one", "many"))
    assert ok, msg


def test_widening_only_the_holder_side_fails():
    """The blunt-wrong answer: the cap never moves."""
    ok, msg = _sharing.check_shared_side_widened(_schema("many", "one"))
    assert not ok and "does not lift it" in msg


def test_widening_both_sides_fails():
    """The blunt-right answer: the cap lifts, and so does a field nobody asked about."""
    ok, msg = _sharing.check_shared_side_widened(_schema("many", "many"))
    assert not ok and "turns" in msg


def test_an_unset_holder_cardinality_counts_as_widened():
    """`cardinality` defaults to many, so omitting it widens that side too."""
    schema = _schema("one", "many")
    del schema["nodes"][0]["relationships"][0]["cardinality"]
    ok, _ = _sharing.check_shared_side_widened(schema)
    assert not ok


# --- comments ------------------------------------------------------------

COMMENTS_REJECTED = [
    pytest.param("# node edges query", id="three-nouns-in-any-order"),
    pytest.param("", id="no-comments"),
    pytest.param(
        "# the query shape changes and stored .gql files break",
        id="no-shape-contrast",
    ),
]


@pytest.mark.parametrize("text", COMMENTS_REJECTED)
def test_content_free_comments_fail(text):
    ok, _ = _sharing.check_comments_cover_query_migration(schema={}, raw_text=text)
    assert not ok


def test_comments_that_contrast_the_shapes_and_name_the_failure_pass():
    ok, msg = _sharing.check_comments_cover_query_migration(
        schema={},
        raw_text=(
            "# Every stored .gql query selecting this relationship changes from\n"
            "# node { ... } to edges { node { ... } }; otherwise it fails with\n"
            "# Cannot query field 'edges' on type 'NestedEdged<Kind>'.\n"
        ),
    )
    assert ok, msg


# --- an unparseable output must not bank checks --------------------------


@pytest.mark.parametrize(
    "name", ["identifier-unique-per-direction", "many-max-count-valid"]
)
def test_an_empty_schema_verifies_nothing(name):
    ok, msg = _schemas.CHECKS[name](schema={})
    assert not ok and "nothing was checked" in msg


# --- the yagni cardinality finding ---------------------------------------

RULE = "yagni-missing-inverse-forces-python-filter"


def _names_cardinality(finding: dict):
    return _audit.check_yagni_finding_names_cardinality(
        [{"rule": RULE, **finding}], RULE
    )


def test_a_cardinality_quoted_in_evidence_does_not_count():
    """The prompt hands over the existing `cardinality: many`."""
    ok, _ = _names_cardinality(
        {
            "replacement": "Add the missing inverse relationship on "
            "InfraInterface back to InfraDevice.",
            "evidence": "the existing declaration reads cardinality: many",
        }
    )
    assert not ok


def test_a_cardinality_in_a_nested_yaml_replacement_counts():
    ok, msg = _names_cardinality(
        {"replacement": {"yaml": "- name: device\n  cardinality: one"}}
    )
    assert ok, msg


def test_a_cardinality_wrapped_across_a_line_counts():
    ok, msg = _names_cardinality(
        {"replacement": "Add the inverse with cardinality:\n            one"}
    )
    assert ok, msg


def test_a_finding_with_no_recommendation_field_fails():
    ok, _ = _names_cardinality({"description": "cardinality one would work"})
    assert not ok
