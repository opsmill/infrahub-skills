"""Assert every SKILL.md carries parseable frontmatter, and that the blocks
deliberately duplicated across the skill-change pipeline stay identical.

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
