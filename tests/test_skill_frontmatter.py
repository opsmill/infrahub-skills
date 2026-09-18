"""Assert every SKILL.md carries parseable frontmatter, that a create-shaped
description also advertises modification work, and that the blocks deliberately
duplicated across the skill-change pipeline stay identical.

Both checks exist because a silent failure was shipped here. `metadata.pipeline`
was rewritten to `skill-change (stage 1 of 3: analyze or grill, ...)`, and an
unquoted YAML scalar containing `: ` is a parse error, so all four pipeline
skills carried invalid frontmatter at once. Nothing caught it: rumdl lints
prose, yamllint only looks at `.yml`/`.yaml`, and no job parses the block a
skill's triggering depends on.

The duplication check guards the other half of the same trade. The
`## Tool usage` block is copied verbatim into all four pipeline skills rather
than linked, on the argument that a constraint an agent must obey
unconditionally is weaker behind a link it may not follow. That argument only
holds while the copies agree; four copies nobody compares is the drift a
reviewer rightly objects to. This test is what makes the copies safe.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent

# The four stages of the skill-change pipeline, which share verbatim blocks.
PIPELINE_SKILLS = [
    "analyzing-skill-bugs",
    "grilling-skill-features",
    "test-driving-skill-changes",
    "implementing-skill-changes",
]

# A description opening on one of these announces the skill as build-only.
CREATION_OPENERS = re.compile(r"\s*(creates?|builds?|generates?|manages)\b", re.I)

# Verb forms that name work on an artifact that already exists. Noun forms are
# deliberately absent: "proposed changes" is a domain noun in the checks skill's
# TRIGGER and names no modification work, while "changing" does.
MODIFICATION_VERBS = [
    "modifying",
    "modify",
    "modifies",
    "modification",
    "editing",
    "updating",
    "update",
    "debugging",
    "debug",
    "extending",
    "extend",
    "changing",
    "refactoring",
    "troubleshooting",
    "investigating",
    "fixing",
]


def _skill_files() -> list[Path]:
    return sorted(ROOT.glob("skills/*/SKILL.md")) + sorted(ROOT.glob(".claude/skills/*/SKILL.md"))


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} does not open with a frontmatter fence"
    return yaml.safe_load(text.split("---\n", 2)[1])


def _section(path: Path, heading: str) -> str:
    """The body of one `## heading` section, up to the next `## `."""
    out, collecting = [], False
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            if collecting:
                break
            collecting = line.strip() == heading
            continue
        if collecting:
            out.append(line)
    assert out, f"{path} has no {heading!r} section"
    return "\n".join(out).strip()


@pytest.mark.parametrize("path", _skill_files(), ids=lambda p: p.parent.name)
def test_frontmatter_parses(path: Path) -> None:
    """Frontmatter is valid YAML and carries the fields triggering depends on."""
    fm = _frontmatter(path)
    assert isinstance(fm, dict), f"{path} frontmatter is not a mapping"
    assert fm.get("name") == path.parent.name, f"{path} name does not match its directory"
    assert fm.get("description"), f"{path} has no description"


def _shipped_skill_files() -> list[Path]:
    return sorted(ROOT.glob("skills/*/SKILL.md"))


# The real `TRIGGER when:`, not the one inside `DO NOT TRIGGER when:`.
TRIGGER_CLAUSE = re.compile(r"(?<!DO NOT )TRIGGER when\s*:", re.I)


def _trigger_scope(description: str) -> str:
    """The `TRIGGER when:` clauses alone.

    Not the lead-in sentence, which says what the skill does rather than when it
    fires, and not `DO NOT TRIGGER`, which lists what must not fire it. A
    modification verb in either place still leaves day-two work with no TRIGGER
    phrase to match against, which is precisely the gap #78 describes. Scoping
    from the top of the description instead would pass "Creates and modifies
    Foo. TRIGGER when: building new Foo." on the lead-in alone. That is not
    hypothetical: managing-schemas passed exactly that way until this was
    tightened.

    An empty string when the description has no TRIGGER clause at all, which
    fails the assertion rather than vacuously satisfying it.
    """
    flat = " ".join(description.split())
    match = TRIGGER_CLAUSE.search(flat)
    if match is None:
        return ""
    return re.split(r"DO NOT TRIGGER", flat[match.end() :], flags=re.I)[0]


def names_modification_intent(description: str) -> bool:
    """True if the `TRIGGER when:` clauses name work on an artifact that exists."""
    scope = _trigger_scope(description)
    return any(re.search(rf"\b{re.escape(verb)}", scope, re.I) for verb in MODIFICATION_VERBS)


# compliant, compliant variant, violating, and two near misses.
INTENT_FIXTURES = [
    pytest.param(
        "Creates, modifies and debugs Infrahub Generators. "
        "TRIGGER when: building design-to-implementation workflows, "
        "modifying or extending an existing generator, changing what a generator produces. "
        "DO NOT TRIGGER when: designing schemas.",
        True,
        id="compliant",
    ),
    pytest.param(
        "Creates Infrahub transforms. "
        "TRIGGER when: debugging why an existing transform renders the wrong output, "
        "updating a template, building config generation, data export. "
        "DO NOT TRIGGER when: designing schemas.",
        True,
        id="compliant-variant",
    ),
    pytest.param(
        "Creates Infrahub custom navigation menus for the web UI sidebar. "
        "TRIGGER when: designing sidebar menus, grouping node types in UI, "
        "customizing Infrahub web interface navigation. "
        "DO NOT TRIGGER when: designing schemas, writing checks or transforms.",
        False,
        id="violating",
    ),
    pytest.param(
        # Carries "changes" as a domain noun inside TRIGGER and a real
        # modification verb inside DO NOT TRIGGER. A substring match over the
        # whole description passes this; neither string triggers anything.
        "Creates Infrahub check definitions. "
        "TRIGGER when: writing validation checks, "
        "building data quality guards for proposed changes. "
        "DO NOT TRIGGER when: modifying schemas, editing data files.",
        False,
        id="violating-near-miss",
    ),
    pytest.param(
        # The lead-in sentence promises modification and the TRIGGER clauses
        # deliver none of it, so day-two work still matches no trigger phrase.
        # managing-schemas shipped in exactly this shape.
        "Creates and modifies Foo. "
        "TRIGGER when: building new Foo, creating Foo from templates. "
        "DO NOT TRIGGER when: designing schemas.",
        False,
        id="violating-lead-in-only",
    ),
]


@pytest.mark.parametrize(("description", "expected"), INTENT_FIXTURES)
def test_modification_intent_detector_discriminates(description: str, expected: bool) -> None:
    """The detector grades substance, not vocabulary.

    The near miss is the case that matters: it contains both "changes" and
    "modifying", and still names no modification trigger.
    """
    assert names_modification_intent(description) is expected


@pytest.mark.parametrize("path", _shipped_skill_files(), ids=lambda p: p.parent.name)
def test_creation_shaped_description_names_modification_triggers(path: Path) -> None:
    """A skill that advertises creation also advertises changing what exists.

    A create-shaped description does not merely omit modification work, it reads
    as a positive signal that the skill does not apply to it. Issue #78 recorded
    the cost: a session asked to investigate an existing generator never invoked
    the skill, and shipped a change that deleted a live interface the generator
    did not own. The skill's front page warned about that exact failure twice.

    Descriptions have no eval coverage, because eval prompts say `Read the skill
    at ...` and so bypass triggering entirely. This is the only surface that can
    fail on one.
    """
    name = path.parent.name
    description = " ".join((_frontmatter(path).get("description") or "").split())
    if not CREATION_OPENERS.match(description):
        pytest.skip(f"{name} does not open on a creation verb")
    assert names_modification_intent(description), (
        f"{name}: the description opens on a creation verb but its `TRIGGER when:` "
        f"clauses name only building. Add modifying / debugging / extending an "
        f"existing artifact to TRIGGER itself, not just to the lead-in sentence, "
        f"so the skill fires on day-two work. TRIGGER clauses were: "
        f"{_trigger_scope(description)!r}"
    )


@pytest.mark.parametrize("name", PIPELINE_SKILLS)
def test_pipeline_skill_metadata(name: str) -> None:
    """The pipeline stage label survives YAML parsing with its colon intact."""
    fm = _frontmatter(ROOT / ".claude/skills" / name / "SKILL.md")
    pipeline = fm.get("metadata", {}).get("pipeline", "")
    assert pipeline.startswith("skill-change (stage "), (
        f"{name}: metadata.pipeline lost its stage label: {pipeline!r}"
    )


def test_tool_usage_blocks_are_identical() -> None:
    """The verbatim `## Tool usage` block does not drift between the four stages."""
    blocks = {n: _section(ROOT / ".claude/skills" / n / "SKILL.md", "## Tool usage") for n in PIPELINE_SKILLS}
    reference = blocks[PIPELINE_SKILLS[0]]
    for name, block in blocks.items():
        assert block == reference, (
            f"{name}'s Tool usage block has drifted from {PIPELINE_SKILLS[0]}'s. "
            "The four copies are deliberate; keeping them identical is the condition."
        )


def test_boundaries_pointer_stays_one_line() -> None:
    """`## Boundaries` links AGENTS.md rather than restating the list."""
    for name in PIPELINE_SKILLS:
        body = _section(ROOT / ".claude/skills" / name / "SKILL.md", "## Boundaries")
        assert "AGENTS.md" in body, f"{name}: Boundaries does not point at AGENTS.md"
        assert len(body.splitlines()) <= 3, (
            f"{name}: Boundaries grew to {len(body.splitlines())} lines. "
            "It is a pointer; the list lives in AGENTS.md."
        )
