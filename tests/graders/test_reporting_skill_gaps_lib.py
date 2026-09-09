"""Tests for the version header checks in graders/reporting-skill-gaps/lib.py.

Covers `states-skills-version` and `states-sdk-version` against filled
headers, unfilled template placeholders, prose that only mentions a
version, and each other: the two lines sit next to each other in the
report header, so a regex that reads one as the other would pass a
report that carries only half the information a maintainer needs.
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

_SKILL_DIR = _REPO_ROOT / "skills" / "infrahub-reporting-skill-gaps"
_TEMPLATE = _SKILL_DIR / "templates" / "skill-friction.md"
_HANDOFF_GRADER = _REPO_ROOT / "graders" / "reporting-skill-gaps" / "check_handoff_to_reporting.py"


FILLED_HEADER = """\
# feat: infrahub-managing-checks: sharing a GraphQL fragment across check modules

**Skill**: infrahub-managing-checks
**Type**: feature
**Confidence**: recurring
**Skills version**: 1.2.8
**Infrahub SDK version**: 1.14.0
**Tracker search**: `repo:opsmill/infrahub-skills fragment import` — no match
"""

UNFILLED_HEADER = """\
**Skill**: [skill directory, e.g. infrahub-managing-schemas]
**Skills version**: [the version of the skills plugin whose guidance failed]
**Infrahub SDK version**: [the infrahub-sdk version this session ran against]
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
    assert "1.14.0" in detail


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
    text = FILLED_HEADER.replace("**Infrahub SDK version**: 1.14.0\n", "")
    passed, detail = check_states_sdk_version(text)
    assert not passed
    assert "no SDK-version header line" in detail


def test_sdk_version_not_satisfied_by_skills_line():
    """A skills-version-only header must not pass as the SDK version."""
    passed, _ = check_states_sdk_version("**Skills version**: 1.2.8\n")
    assert not passed


def test_sdk_version_rejects_version_only_in_prose():
    text = "The SDK we were on shipped 1.14.0, which is where the flag moved.\n"
    passed, _ = check_states_sdk_version(text)
    assert not passed


# ---------------------------------------------------------------------------
# Wiring: registry, template, and eval grader stay in step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["states-skills-version", "states-sdk-version"])
def test_check_is_registered(name):
    assert name in CHECKS


@pytest.mark.parametrize("line", ["**Skills version**", "**Infrahub SDK version**"])
def test_template_carries_header_line(line):
    """The graded field has to exist in the template the skill fills."""
    assert line in _TEMPLATE.read_text()


@pytest.mark.parametrize("name", ["states-skills-version", "states-sdk-version"])
def test_handoff_grader_runs_check(name):
    assert name in _HANDOFF_GRADER.read_text()
