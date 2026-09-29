"""Tests for scripts/check-skill-registration.py.

A new skill has to appear on every surface a reader picks skills from, and
`dev/guidelines/skill-registration.md` lists them. The list alone did not
hold: #159 wired the five surfaces it named and missed the router, and
`dev/guides/getting-started.md` fell seven skills behind across earlier
additions. So the surfaces are checked, not trusted (#160).

Each surface is parsed: the table a row has to sit in, the tree an entry has
to sit in, the headings a page has to carry. The near-miss tests put the
skill's name on the surface but outside the structure that counts, which a
substring match would pass.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = ROOT / "scripts" / "check-skill-registration.py"


def _load():
    if not _SCRIPT.is_file():
        pytest.fail(
            "scripts/check-skill-registration.py does not exist: nothing checks "
            "that a user-invocable skill appears on every registration surface"
        )
    spec = importlib.util.spec_from_file_location("check_skill_registration", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load()


# The surface labels the script reports, one per place a skill must appear.
AGENTS = "AGENTS.md"
README_TABLE = "README.md skills table"
README_TREE = "README.md project tree"
FRONT_PAGE = "docs/docs/readme.mdx"
ROUTER = "docs/docs/choosing-a-skill.mdx"
ROUTER_COUNT = "docs/docs/choosing-a-skill.mdx skill count"
MANIFEST = ".github/.release-manifest.json"
PAGE_SECTIONS = "reference page sections"

SECTIONS = [
    "When to use",
    "What it produces",
    "Example prompts",
    "Key rules enforced",
    "Common mistakes it catches",
]
NOT_SURE = "Not sure this is the right skill?"

# name, display name, lifecycle group in the router
SKILLS = [
    ("infrahub-alpha-widgets", "Widget Maker", "Build your model"),
    ("infrahub-beta-gadgets", "Gadget Fixer", "Automate"),
]


def _short(name: str) -> str:
    return name.removeprefix("infrahub-")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture edit did not apply: {old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _page(name: str, display: str, extra: list[str] | None = None) -> str:
    body = f"---\ntitle: {display}\n---\n\nSkill: `{name}`\n\nIntro.\n"
    for heading in SECTIONS + (extra or []):
        body += f"\n## {heading}\n\nText.\n"
    return body


def _tree(root: Path, count_word: str = "Two") -> Path:
    """A compliant tree: two user-invocable skills and one exempt one."""
    for name, _display, _group in SKILLS:
        _write(
            root / "skills" / name / "SKILL.md", f"---\nname: {name}\n---\n\nBody.\n"
        )
    _write(
        root / "skills" / "infrahub-common" / "SKILL.md",
        "---\nname: infrahub-common\nuser-invocable: false\n---\n\nShared.\n",
    )

    agents_rows = "".join(
        f"| `{n}` | `skills/{n}/` | Does {_short(n)} |\n" for n, _d, _g in SKILLS
    )
    _write(
        root / "AGENTS.md",
        "# AGENTS.md\n\n## Commands\n\n| Task | Command |\n| --- | --- |\n"
        "| Test | `uv run invoke test` |\n\n"
        "## Quick Reference\n\n### Skills\n\n"
        "| Skill | Directory | Description |\n| ------- | ----------- | ------------- |\n"
        f"{agents_rows}\n### Rule = Test (Required)\n\nProse.\n",
    )

    readme_rows = "".join(
        f"| **{_short(n)}** | Does {_short(n)} |\n" for n, _d, _g in SKILLS
    )
    tree_rows = "".join(f"│   ├── {n}/  # {_short(n)}\n" for n, _d, _g in SKILLS)
    _write(
        root / "README.md",
        "# Skills\n\n## Install\n\n```bash\nnpx skills add opsmill/infrahub-skills\n```\n\n"
        f"## Skills\n\n| Skill | What it does |\n| ----- | ------------ |\n{readme_rows}\n"
        "Each skill lives in `skills/infrahub-<name>/`.\n\n"
        "## Project Structure\n\n```text\n.\n├── skills/\n"
        f"│   ├── infrahub-common/          # Shared references\n{tree_rows}"
        "├── README.md\n└── LICENSE\n```\n\n## Resources\n\n- Link\n",
    )

    front_rows = "".join(
        f"| [{d}](./skills-reference/{_short(n)}.mdx) | Does {_short(n)} | `{n}` |\n"
        for n, d, _g in SKILLS
    )
    _write(
        root / "docs" / "docs" / "readme.mdx",
        "---\ntitle: Home\n---\n\n## When you would reach for it\n\nScenarios.\n\n"
        "## Skills included\n\n| Skill | What it does | Skill name |\n"
        f"| ------- | ------------- | ------- |\n{front_rows}\n"
        "A shared reference library (`infrahub-common`) backs them.\n\n## Compatibility\n\nText.\n",
    )

    groups = ""
    for name, display, group in SKILLS:
        groups += (
            f"### {group}\n\n| You have | You want | Go to |\n| --- | --- | --- |\n"
            f"| Something | Something else | [{display}](./skills-reference/{_short(name)}.mdx) |\n\n"
        )
    _write(
        root / "docs" / "docs" / "choosing-a-skill.mdx",
        "---\ntitle: Which skill do I use?\n---\n\n"
        f"{count_word} skills is a lot to hold in your head. Start from what you have.\n\n"
        f"## Start from what you have\n\nSkim the group.\n\n{groups}"
        "## You do not have to choose\n\nDescribe the task and the right skill fires.\n",
    )

    _write(
        root / ".github" / ".release-manifest.json",
        json.dumps(
            {"version": "1.0.0", "skills": [n for n, _d, _g in SKILLS]}, indent=2
        ),
    )

    for name, display, _group in SKILLS:
        _write(
            root / "docs" / "docs" / "skills-reference" / f"{_short(name)}.mdx",
            _page(name, display),
        )
    return root


WIDGETS = SKILLS[0][0]
ROUTER_PATH = Path("docs") / "docs" / "choosing-a-skill.mdx"


def _add_pair_table(root: Path, heading: str) -> None:
    _edit(
        root / ROUTER_PATH,
        "## You do not have to choose",
        "## Pairs that are easy to confuse\n\n"
        f"### {heading}\n\n"
        "| Use Widget Maker when... | Use Gadget Fixer when... |\n| --- | --- |\n"
        "| You need a widget | You need a gadget fixed |\n\n"
        "## You do not have to choose",
    )


# --- compliant ------------------------------------------------------------


def test_compliant_tree_passes(mod, tmp_path: Path) -> None:
    assert mod.check_registration(_tree(tmp_path)) == []


def test_exempt_skill_is_required_nowhere(mod, tmp_path: Path) -> None:
    """`infrahub-common` declares `user-invocable: false` and is on no surface.
    The count word stays "Two": the exempt skill is not counted either."""
    root = _tree(tmp_path)
    failures = mod.check_registration(root)
    assert not [f for f in failures if f[0] == "infrahub-common"]
    assert failures == []


def test_compliant_variant_passes(mod, tmp_path: Path) -> None:
    """Refactored the way a parser is vulnerable to: both router rows in one
    group, padded cells with trailing prose, a tree entry with no comment,
    extra sections on a page, and a pair table whose skills carry the
    "Not sure" section after those extras."""
    root = _tree(tmp_path)
    router = root / ROUTER_PATH
    _edit(
        router,
        "\n\n### Automate\n\n| You have | You want | Go to |\n| --- | --- | --- |\n",
        "\n",
    )
    _edit(
        router,
        "| Something | Something else | [Widget Maker](./skills-reference/alpha-widgets.mdx) |",
        "|  Something  |  Something else  |  [Widget Maker](./skills-reference/alpha-widgets.mdx), "
        "then review it  |",
    )
    _edit(
        root / "README.md",
        f"│   ├── {WIDGETS}/  # alpha-widgets\n",
        f"│   └── {WIDGETS}/\n",
    )
    _edit(root / "AGENTS.md", f"| `{WIDGETS}` |", f"|   `{WIDGETS}`   |")
    _add_pair_table(root, "Widget Maker, Gadget Fixer")
    for name, display, _group in SKILLS:
        _write(
            root / "docs" / "docs" / "skills-reference" / f"{_short(name)}.mdx",
            _page(name, display, extra=["Running it", "How it works", NOT_SURE]),
        )
    assert mod.check_registration(root) == []


def test_pair_heading_naming_no_skill_is_ignored(mod, tmp_path: Path) -> None:
    """The real router has a heading like "Concept Tutor, the managing skills,
    Data Analyzer". A part that is not a router display name names no page,
    so it requires no "Not sure" section anywhere."""
    root = _tree(tmp_path)
    _add_pair_table(root, "Widget Maker, the managing skills")
    _write(
        root / "docs" / "docs" / "skills-reference" / f"{_short(WIDGETS)}.mdx",
        _page(WIDGETS, "Widget Maker", extra=[NOT_SURE]),
    )
    assert mod.check_registration(root) == []


def test_missing_reference_page_is_left_to_its_own_check(mod, tmp_path: Path) -> None:
    """Page existence belongs to check-docs-skill-names.py. This script must
    not crash on a missing page, nor report it a second time."""
    root = _tree(tmp_path)
    (root / "docs" / "docs" / "skills-reference" / f"{_short(WIDGETS)}.mdx").unlink()
    assert (WIDGETS, PAGE_SECTIONS) not in mod.check_registration(root)


# --- violating: each surface removed in turn ------------------------------


def _drop_agents(root: Path) -> None:
    _edit(
        root / "AGENTS.md",
        f"| `{WIDGETS}` | `skills/{WIDGETS}/` | Does alpha-widgets |\n",
        "",
    )


def _drop_readme_table(root: Path) -> None:
    _edit(root / "README.md", "| **alpha-widgets** | Does alpha-widgets |\n", "")


def _drop_readme_tree(root: Path) -> None:
    _edit(root / "README.md", f"│   ├── {WIDGETS}/  # alpha-widgets\n", "")


def _drop_front_page(root: Path) -> None:
    _edit(
        root / "docs" / "docs" / "readme.mdx",
        f"| [Widget Maker](./skills-reference/alpha-widgets.mdx) | Does alpha-widgets | `{WIDGETS}` |\n",
        "",
    )


def _drop_router(root: Path) -> None:
    _edit(
        root / ROUTER_PATH,
        "| Something | Something else | [Widget Maker](./skills-reference/alpha-widgets.mdx) |\n",
        "",
    )


def _drop_manifest(root: Path) -> None:
    path = root / ".github" / ".release-manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["skills"].remove(WIDGETS)
    path.write_text(json.dumps(data), encoding="utf-8")


def _drop_section(root: Path) -> None:
    page = root / "docs" / "docs" / "skills-reference" / f"{_short(WIDGETS)}.mdx"
    _edit(page, "\n## Key rules enforced\n\nText.\n", "")


@pytest.mark.parametrize(
    ("mutate", "surface"),
    [
        (_drop_agents, AGENTS),
        (_drop_readme_table, README_TABLE),
        (_drop_readme_tree, README_TREE),
        (_drop_front_page, FRONT_PAGE),
        (_drop_router, ROUTER),
        (_drop_manifest, MANIFEST),
        (_drop_section, PAGE_SECTIONS),
    ],
    ids=[
        "agents",
        "readme-table",
        "readme-tree",
        "front-page",
        "router",
        "manifest",
        "sections",
    ],
)
def test_skill_missing_from_a_surface_is_reported(
    mod, tmp_path: Path, mutate, surface
) -> None:
    root = _tree(tmp_path)
    mutate(root)
    assert mod.check_registration(root) == [(WIDGETS, surface)]


def test_wrong_router_count_is_reported(mod, tmp_path: Path) -> None:
    root = _tree(tmp_path, count_word="Three")
    assert mod.check_registration(root) == [("", ROUTER_COUNT)]


def test_unrecognized_router_count_is_reported(mod, tmp_path: Path) -> None:
    """A count the script cannot read is a failure, not a skip: otherwise
    rewording the sentence silently turns the count check off."""
    root = _tree(tmp_path, count_word="Many")
    assert mod.check_registration(root) == [("", ROUTER_COUNT)]


def test_pair_skill_without_not_sure_section_is_reported(mod, tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _add_pair_table(root, "Widget Maker, Gadget Fixer")
    _write(
        root / "docs" / "docs" / "skills-reference" / f"{_short(WIDGETS)}.mdx",
        _page(WIDGETS, "Widget Maker", extra=[NOT_SURE]),
    )
    assert mod.check_registration(root) == [(SKILLS[1][0], PAGE_SECTIONS)]


def test_not_sure_section_on_a_page_with_no_pair_table_is_reported(
    mod, tmp_path: Path
) -> None:
    """The section is conditional both ways: it points readers at a pair table,
    so a page carrying it with no pair table behind it points at nothing."""
    root = _tree(tmp_path)
    _write(
        root / "docs" / "docs" / "skills-reference" / f"{_short(WIDGETS)}.mdx",
        _page(WIDGETS, "Widget Maker", extra=[NOT_SURE]),
    )
    assert mod.check_registration(root) == [(WIDGETS, PAGE_SECTIONS)]


# --- violating near misses: the name is there, the structure is not -------


def test_agents_mention_outside_the_skills_table_is_reported(
    mod, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    _drop_agents(root)
    _edit(
        root / "AGENTS.md",
        "### Rule = Test (Required)\n\nProse.\n",
        f"### Rule = Test (Required)\n\nProse about `{WIDGETS}`.\n",
    )
    _edit(
        root / "AGENTS.md",
        "| Test | `uv run invoke test` |\n",
        f"| Test | `uv run invoke test` |\n| `{WIDGETS}` | `skillgrade --eval=widgets` |\n",
    )
    assert mod.check_registration(root) == [(WIDGETS, AGENTS)]


def test_readme_mention_outside_the_skills_table_is_reported(
    mod, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    _drop_readme_table(root)
    _edit(
        root / "README.md",
        "npx skills add opsmill/infrahub-skills\n",
        "npx skills add opsmill/infrahub-skills --skill alpha-widgets\n",
    )
    _edit(
        root / "README.md",
        "Each skill lives in `skills/infrahub-<name>/`.\n",
        "Each skill lives in `skills/infrahub-<name>/`, **alpha-widgets** included.\n",
    )
    assert mod.check_registration(root) == [(WIDGETS, README_TABLE)]


def test_readme_tree_mention_only_in_a_comment_is_reported(mod, tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _drop_readme_tree(root)
    _edit(
        root / "README.md",
        "│   ├── infrahub-common/          # Shared references\n",
        f"│   ├── infrahub-common/          # Shared references, used by {WIDGETS}/\n",
    )
    assert mod.check_registration(root) == [(WIDGETS, README_TREE)]


def test_front_page_mention_outside_the_skills_table_is_reported(
    mod, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    _drop_front_page(root)
    _edit(
        root / "docs" / "docs" / "readme.mdx",
        "Scenarios.\n",
        f"Scenarios, like the [Widget Maker](./skills-reference/alpha-widgets.mdx) (`{WIDGETS}`).\n",
    )
    assert mod.check_registration(root) == [(WIDGETS, FRONT_PAGE)]


def test_router_mention_outside_a_start_table_is_reported(mod, tmp_path: Path) -> None:
    """Linked from the "You do not have to choose" prose and from a pair-table
    body cell, but in no "You have | You want | Go to" row."""
    root = _tree(tmp_path)
    _drop_router(root)
    _add_pair_table(root, "Gadget Fixer, the managing skills")
    _edit(
        root / ROUTER_PATH,
        "| You need a widget |",
        "| You need a [Widget Maker](./skills-reference/alpha-widgets.mdx) widget |",
    )
    _edit(
        root / ROUTER_PATH,
        "Describe the task and the right skill fires.\n",
        "Describe the task and the right skill fires, even the "
        "[Widget Maker](./skills-reference/alpha-widgets.mdx).\n",
    )
    gadgets = SKILLS[1]
    _write(
        root / "docs" / "docs" / "skills-reference" / f"{_short(gadgets[0])}.mdx",
        _page(gadgets[0], gadgets[1], extra=[NOT_SURE]),
    )
    assert mod.check_registration(root) == [(WIDGETS, ROUTER)]


def test_manifest_name_outside_the_skills_array_is_reported(
    mod, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    path = root / ".github" / ".release-manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["skills"].remove(WIDGETS)
    data["notes"] = f"{WIDGETS} is new in this release"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert mod.check_registration(root) == [(WIDGETS, MANIFEST)]


@pytest.mark.parametrize(
    "page_body",
    [
        # every heading present, two of them swapped
        _page(WIDGETS, "Widget Maker").replace(
            "## What it produces\n\nText.\n\n## Example prompts",
            "## Example prompts\n\nText.\n\n## What it produces",
        ),
        # every heading present, one demoted to ###
        _page(WIDGETS, "Widget Maker").replace(
            "## Key rules enforced", "### Key rules enforced"
        ),
        # heading text present only as prose
        _page(WIDGETS, "Widget Maker").replace(
            "## Key rules enforced\n", "The Key rules enforced are below.\n"
        ),
        # heading text present only inside a fenced block
        _page(WIDGETS, "Widget Maker").replace("\n## Key rules enforced\n\nText.\n", "")
        + "\n```markdown\n## Key rules enforced\n```\n",
    ],
    ids=["out-of-order", "demoted", "prose", "fenced"],
)
def test_section_text_without_the_section_is_reported(
    mod, tmp_path: Path, page_body: str
) -> None:
    root = _tree(tmp_path)
    _write(
        root / "docs" / "docs" / "skills-reference" / f"{_short(WIDGETS)}.mdx",
        page_body,
    )
    assert mod.check_registration(root) == [(WIDGETS, PAGE_SECTIONS)]


# --- the live tree and the wiring -----------------------------------------


def test_real_repo_is_registered_everywhere(mod) -> None:
    """The live check, as CI runs it."""
    assert mod.check_registration(ROOT) == []


def test_main_passes_on_the_real_repo(mod) -> None:
    assert mod.main() == 0


def test_main_fails_when_it_finds_no_skills(
    mod, tmp_path: Path, monkeypatch, capsys
) -> None:
    """A check that finds nothing must not report success, or a moved
    skills/ directory reports clean having checked nothing."""
    (tmp_path / "skills").mkdir()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.main() == 1
    assert "no" in capsys.readouterr().out.lower()


def test_lint_task_runs_the_check() -> None:
    tree = ast.parse((ROOT / "tasks.py").read_text(encoding="utf-8"))
    lint = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "lint"
    )
    commands = [
        call.args[0].value
        for call in ast.walk(lint)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "run"
        and call.args
        and isinstance(call.args[0], ast.Constant)
    ]
    assert "uv run python scripts/check-skill-registration.py" in commands


def test_ci_runs_the_check() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    runs = [
        step.get("run", "").strip()
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    ]
    assert "python scripts/check-skill-registration.py" in runs
