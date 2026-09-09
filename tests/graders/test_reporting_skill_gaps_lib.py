"""Tests for the version header checks in graders/reporting-skill-gaps/lib.py.

Covers `states-skills-version`, `states-sdk-version`, and
`states-infrahub-version` against filled headers, unfilled template
placeholders, prose that only mentions a version, and each other: the
three lines sit adjacent in the report header and two of them start with
"Infrahub", so a regex that reads one as another would pass a report
carrying only part of the information a maintainer needs.
"""

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the module directly — the hyphenated directory is not a valid Python
# package name, so we use importlib.util to load lib.py by file path.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "reporting-skill-gaps" / "lib.py"
_spec = importlib.util.spec_from_file_location("skill_gaps_graders_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CHECKS = _mod.CHECKS
check_states_skills_version = _mod.check_states_skills_version
check_states_sdk_version = _mod.check_states_sdk_version
check_states_infrahub_version = _mod.check_states_infrahub_version

_SKILL_DIR = _REPO_ROOT / "skills" / "infrahub-reporting-skill-gaps"
_TEMPLATE = _SKILL_DIR / "templates" / "skill-friction.md"
_HANDOFF_GRADER = _REPO_ROOT / "graders" / "reporting-skill-gaps" / "check_handoff_to_reporting.py"


FILLED_HEADER = """\
# feat: infrahub-managing-checks: sharing a GraphQL fragment across check modules

**Skill**: infrahub-managing-checks
**Type**: feature
**Confidence**: recurring
**Skills version**: 1.2.8
**Infrahub SDK version**: 1.23.2
**Infrahub version**: 1.11.2
**Tracker search**: `repo:opsmill/infrahub-skills fragment import` — no match
"""

UNFILLED_HEADER = """\
**Skill**: [skill directory, e.g. infrahub-managing-schemas]
**Skills version**: [the version of the skills plugin whose guidance failed]
**Infrahub SDK version**: [the infrahub-sdk version this session ran against]
**Infrahub version**: [the version of the Infrahub the session talked to]
"""


# ---------------------------------------------------------------------------
# states-skills-version
# ---------------------------------------------------------------------------


def test_skills_version_accepts_filled_header():
    passed, detail = check_states_skills_version(FILLED_HEADER)
    assert passed
    assert "1.2.8" in detail


def test_skills_version_accepts_unknown():
    passed, _ = check_states_skills_version("**Skills version**: unknown\n")
    assert passed


def test_skills_version_rejects_unfilled_placeholder():
    passed, detail = check_states_skills_version(UNFILLED_HEADER)
    assert not passed
    assert "placeholder" in detail


def test_skills_version_rejects_version_only_in_prose():
    text = "The guidance was wrong; this still worked back in 1.2.7 though.\n"
    passed, _ = check_states_skills_version(text)
    assert not passed


def test_skills_version_not_satisfied_by_sdk_line():
    """An SDK-only header must not pass as the skills version."""
    passed, _ = check_states_skills_version("**Infrahub SDK version**: 1.14.0\n")
    assert not passed


# ---------------------------------------------------------------------------
# states-sdk-version
# ---------------------------------------------------------------------------


def test_sdk_version_accepts_filled_header():
    passed, detail = check_states_sdk_version(FILLED_HEADER)
    assert passed
    assert "1.23.2" in detail


@pytest.mark.parametrize(
    "line",
    [
        "**Infrahub SDK version**: 1.14.0\n",
        "**SDK version**: v1.14\n",
        "- SDK version: 1.14.0b1\n",
        "**infrahub-sdk version**: unknown\n",
    ],
)
def test_sdk_version_accepts_header_variants(line):
    passed, _ = check_states_sdk_version(line)
    assert passed


def test_sdk_version_rejects_unfilled_placeholder():
    passed, detail = check_states_sdk_version(UNFILLED_HEADER)
    assert not passed
    assert "placeholder" in detail


def test_sdk_version_rejects_missing_line():
    text = FILLED_HEADER.replace("**Infrahub SDK version**: 1.23.2\n", "")
    passed, detail = check_states_sdk_version(text)
    assert not passed
    assert "no SDK-version header line" in detail


def test_sdk_version_rejects_version_only_in_prose():
    text = "The SDK we were on shipped 1.23.2, which is where the flag moved.\n"
    passed, _ = check_states_sdk_version(text)
    assert not passed


# ---------------------------------------------------------------------------
# states-infrahub-version
# ---------------------------------------------------------------------------


def test_infrahub_version_accepts_filled_header():
    passed, detail = check_states_infrahub_version(FILLED_HEADER)
    assert passed
    assert "1.11.2" in detail


@pytest.mark.parametrize(
    "line",
    [
        "**Infrahub version**: 1.11.2\n",
        "**Infrahub server version**: 1.11.2\n",
        "- Infrahub version: unknown\n",
        # `infrahubctl info` prints N/A when no server is reachable.
        "**Infrahub version**: N/A\n",
    ],
)
def test_infrahub_version_accepts_header_variants(line):
    passed, _ = check_states_infrahub_version(line)
    assert passed


def test_infrahub_version_rejects_unfilled_placeholder():
    passed, detail = check_states_infrahub_version(UNFILLED_HEADER)
    assert not passed
    assert "placeholder" in detail


def test_infrahub_version_rejects_missing_line():
    text = FILLED_HEADER.replace("**Infrahub version**: 1.11.2\n", "")
    passed, detail = check_states_infrahub_version(text)
    assert not passed
    assert "no Infrahub-version header line" in detail


def test_infrahub_version_rejects_version_only_in_prose():
    text = "We were running Infrahub 1.11.2 at the time, for what it is worth.\n"
    passed, _ = check_states_infrahub_version(text)
    assert not passed


# ---------------------------------------------------------------------------
# The three header lines must not satisfy each other's checks
# ---------------------------------------------------------------------------

_CHECK_FOR_LINE = {
    "**Skills version**: 1.2.8\n": check_states_skills_version,
    "**Infrahub SDK version**: 1.23.2\n": check_states_sdk_version,
    "**Infrahub version**: 1.11.2\n": check_states_infrahub_version,
}


@pytest.mark.parametrize("line", list(_CHECK_FOR_LINE))
@pytest.mark.parametrize("other_line", list(_CHECK_FOR_LINE))
def test_header_lines_do_not_cross_satisfy(line, other_line):
    """Each line satisfies its own check and no other.

    "Infrahub SDK version" and "Infrahub version" share a prefix, so a
    loose regex on either would let a report pass while missing a version
    a maintainer needs.
    """
    check = _CHECK_FOR_LINE[other_line]
    passed, _ = check(line)
    assert passed is (line == other_line)


# ---------------------------------------------------------------------------
# Wiring: registry, template, and eval grader stay in step
# ---------------------------------------------------------------------------


_CHECK_NAMES = [
    "states-skills-version",
    "states-sdk-version",
    "states-infrahub-version",
]


@pytest.mark.parametrize("name", _CHECK_NAMES)
def test_check_is_registered(name):
    assert name in CHECKS


@pytest.mark.parametrize(
    "line",
    ["**Skills version**", "**Infrahub SDK version**", "**Infrahub version**"],
)
def test_template_carries_header_line(line):
    """The graded field has to exist in the template the skill fills."""
    assert line in _TEMPLATE.read_text()


@pytest.mark.parametrize("name", _CHECK_NAMES)
def test_handoff_grader_runs_check(name):
    assert name in _HANDOFF_GRADER.read_text()
