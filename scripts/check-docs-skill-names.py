#!/usr/bin/env python3
"""Check every skills-reference page names a skill that exists.

Each page under docs/docs/skills-reference/ states the skill it documents,
so a reader can map a display name like "Concept Tutor" to the directory
under skills/. That name is prose: renaming a skill does not touch it, and
nothing else in the build compares the two.

This repository has shipped wrong paths into docs twice, which is why the
mapping is checked rather than trusted.

Usage::

    python scripts/check-docs-skill-names.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "docs" / "skills-reference"
SKILLS = ROOT / "skills"

# The line each page carries, for example:  Skill: `infrahub-managing-schemas`
_SKILL_LINE = re.compile(r"^Skill:\s*`(infrahub-[a-z0-9-]+)`\s*$", re.MULTILINE)

# A skill opts out of needing a reference page by declaring itself not
# user-invocable in its own frontmatter — `infrahub-common` is the one
# example, a shared-references directory rather than something a reader
# looks up directly. Deriving the exemption from the skill's own claim,
# rather than naming it here, means a second skill in the same position
# needs no change to this script.
_USER_INVOCABLE_FALSE = re.compile(r"^user-invocable:\s*false\s*$", re.MULTILINE)

# The `---`-delimited block a SKILL.md opens with. Frontmatter is scanned
# in isolation, not the whole file, because a skill's body is free to show
# an example of frontmatter shape (another skill's, or its own) inside a
# fenced code block: text that reads exactly like a real
# `user-invocable: false` line at column 0 without being one.
_FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)


def _frontmatter(skill_md_text: str) -> str:
    """The frontmatter block of a SKILL.md's text, or "" if it has none."""
    match = _FRONTMATTER.match(skill_md_text)
    return match.group(1) if match else ""


def check_skill_names(docs_dir: Path, skills_dir: Path) -> list[tuple[str, str]]:
    """Return (page, claimed skill) for each page whose claim does not resolve.

    A page with no skill line is reported with an empty claim: the line is
    required, so a missing one is the same defect as a wrong one.

    The claim has to match `infrahub-` plus the page's own filename, not
    merely name *some* directory under skills/ — otherwise rewriting
    managing-schemas.mdx to claim infrahub-managing-objects passes, because
    that directory really exists, just not for this page.
    """
    bad: list[tuple[str, str]] = []
    for page in sorted(docs_dir.glob("*.mdx")):
        match = _SKILL_LINE.search(page.read_text(encoding="utf-8"))
        if match is None:
            bad.append((page.name, ""))
            continue
        claimed = match.group(1)
        expected = f"infrahub-{page.stem}"
        if claimed != expected or not (skills_dir / claimed).is_dir():
            bad.append((page.name, claimed))
    return bad


def check_skill_directories(docs_dir: Path, skills_dir: Path) -> list[str]:
    """Return skill directory names with no skills-reference page.

    `check_skill_names` only ever walks pages, so a skill added with no
    page — `mkdir skills/infrahub-managing-widgets` and nothing else —
    passed unnoticed. Walking skills/ too closes the other direction.
    """
    referenced: set[str] = set()
    for page in docs_dir.glob("*.mdx"):
        match = _SKILL_LINE.search(page.read_text(encoding="utf-8"))
        if match is not None:
            referenced.add(match.group(1))

    missing: list[str] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in referenced:
            continue
        skill_md = skill_dir / "SKILL.md"
        skill_md_text = skill_md.read_text(encoding="utf-8") if skill_md.is_file() else ""
        if _USER_INVOCABLE_FALSE.search(_frontmatter(skill_md_text)):
            continue
        missing.append(skill_dir.name)
    return missing


def main() -> int:
    pages = len(list(DOCS.glob("*.mdx")))
    if not pages:
        print(f"FAIL: no docs pages found under {DOCS}.")
        return 1

    bad = check_skill_names(DOCS, SKILLS)
    missing = check_skill_directories(DOCS, SKILLS)
    if not bad and not missing:
        print(
            f"OK: all {pages} skills-reference pages name a skill that exists, "
            "and every user-invocable skill has one."
        )
        return 0

    if bad:
        print(f"FAIL: {len(bad)} skills-reference page(s) with a bad skill name.\n")
        for page, claimed in bad:
            if claimed:
                print(
                    f"  {page}: names `{claimed}`, which is not "
                    "`infrahub-` + this page's own filename, or not a directory under skills/"
                )
            else:
                print(f"  {page}: carries no `Skill: \\`infrahub-...\\`` line")
        print("\nAdd or correct the line so it matches the directory under skills/.")

    if missing:
        if bad:
            print()
        print(f"FAIL: {len(missing)} skill(s) under skills/ with no skills-reference page.\n")
        for name in missing:
            print(f"  {name}")
        print(
            "\nAdd docs/docs/skills-reference/<name>.mdx, or mark the skill "
            "`user-invocable: false` if it is a shared reference like infrahub-common."
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
