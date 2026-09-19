"""Tests for scripts/check-docs-skill-names.py.

Each skills-reference page now names the skill it documents. That name is
prose, so nothing else stops it drifting from the real directory under
skills/. Two wrong paths already shipped into docs in this repository's
history, which is why this is a check and not a convention.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = ROOT / "scripts" / "check-docs-skill-names.py"
_spec = importlib.util.spec_from_file_location("check_docs_skill_names", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

check_skill_names = mod.check_skill_names
check_skill_directories = mod.check_skill_directories


def _page(root: Path, name: str, skill: str | None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    body = "---\ntitle: Thing\n---\n\n"
    if skill is not None:
        body += f"Skill: `{skill}`\n"
    (root / name).write_text(body, encoding="utf-8")


def _skill(root: Path, name: str, *, user_invocable: bool = True) -> None:
    d = root / name
    d.mkdir(parents=True)
    body = f"---\nname: {name}\n"
    if not user_invocable:
        body += "user-invocable: false\n"
    body += "---\n\nBody.\n"
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_matching_name_is_not_reported(tmp_path: Path) -> None:
    docs = tmp_path / "skills-reference"
    skills = tmp_path / "skills"
    _page(docs, "managing-schemas.mdx", "infrahub-managing-schemas")
    (skills / "infrahub-managing-schemas").mkdir(parents=True)
    assert check_skill_names(docs, skills) == []


def test_nonexistent_skill_is_reported(tmp_path: Path) -> None:
    """The defect this script exists to catch."""
    docs = tmp_path / "skills-reference"
    skills = tmp_path / "skills"
    _page(docs, "managing-schemas.mdx", "infrahub-managing-schemer")
    (skills / "infrahub-managing-schemas").mkdir(parents=True)
    assert check_skill_names(docs, skills) == [
        ("managing-schemas.mdx", "infrahub-managing-schemer")
    ]


def test_page_with_no_skill_line_is_reported(tmp_path: Path) -> None:
    docs = tmp_path / "skills-reference"
    skills = tmp_path / "skills"
    _page(docs, "managing-schemas.mdx", None)
    (skills / "infrahub-managing-schemas").mkdir(parents=True)
    assert check_skill_names(docs, skills) == [("managing-schemas.mdx", "")]


def test_wrong_existing_skill_is_reported(tmp_path: Path) -> None:
    """The defect this fix closes: the claimed skill is a real directory,
    just not the one this page's own filename says it documents. Rewriting
    managing-schemas.mdx to claim infrahub-managing-objects used to pass,
    because `is_dir()` only asserts the claimed skill exists somewhere."""
    docs = tmp_path / "skills-reference"
    skills = tmp_path / "skills"
    _page(docs, "managing-schemas.mdx", "infrahub-managing-objects")
    (skills / "infrahub-managing-objects").mkdir(parents=True)
    (skills / "infrahub-managing-schemas").mkdir(parents=True)
    assert check_skill_names(docs, skills) == [
        ("managing-schemas.mdx", "infrahub-managing-objects")
    ]


def test_real_repo_pages_all_name_a_real_skill() -> None:
    """The live check, as CI runs it."""
    bad = check_skill_names(ROOT / "docs" / "docs" / "skills-reference", ROOT / "skills")
    assert bad == []


def test_skill_with_no_page_is_reported(tmp_path: Path) -> None:
    """The defect this fix closes: the loop only ever walked pages, never
    skills, so `mkdir skills/infrahub-managing-widgets` with no reference
    page still reported OK."""
    docs = tmp_path / "skills-reference"
    skills = tmp_path / "skills"
    _page(docs, "managing-schemas.mdx", "infrahub-managing-schemas")
    (skills / "infrahub-managing-schemas").mkdir(parents=True)
    (skills / "infrahub-managing-widgets").mkdir(parents=True)
    assert check_skill_directories(docs, skills) == ["infrahub-managing-widgets"]


def test_non_user_invocable_skill_with_no_page_is_not_reported(tmp_path: Path) -> None:
    """`infrahub-common` is a shared-reference directory, not something a
    reader looks up directly, and it declares that itself with
    `user-invocable: false` — the exemption is derived from that field
    rather than hardcoding the skill's name."""
    docs = tmp_path / "skills-reference"
    skills = tmp_path / "skills"
    docs.mkdir(parents=True)
    _skill(skills, "infrahub-common", user_invocable=False)
    assert check_skill_directories(docs, skills) == []


def test_real_repo_skills_all_have_a_page() -> None:
    """The live check, as CI runs it."""
    missing = check_skill_directories(
        ROOT / "docs" / "docs" / "skills-reference", ROOT / "skills"
    )
    assert missing == []


def test_empty_docs_dir_fails(tmp_path: Path, capsys, monkeypatch) -> None:
    """A check that finds nothing must not report success.

    check_skill_names itself returns [] for an empty directory, which is
    correct: there are no bad pages. main() is where that has to fail, or a
    moved docs directory would report clean having checked nothing.
    """
    docs = tmp_path / "skills-reference"
    docs.mkdir(parents=True)
    (tmp_path / "skills").mkdir()
    monkeypatch.setattr(mod, "DOCS", docs)
    monkeypatch.setattr(mod, "SKILLS", tmp_path / "skills")
    assert mod.main() == 1
    assert "no" in capsys.readouterr().out.lower()
