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


def check_skill_names(docs_dir: Path, skills_dir: Path) -> list[tuple[str, str]]:
    """Return (page, claimed skill) for each page whose claim does not resolve.

    A page with no skill line is reported with an empty claim: the line is
    required, so a missing one is the same defect as a wrong one.
    """
    bad: list[tuple[str, str]] = []
    for page in sorted(docs_dir.glob("*.mdx")):
        match = _SKILL_LINE.search(page.read_text(encoding="utf-8"))
        if match is None:
            bad.append((page.name, ""))
        elif not (skills_dir / match.group(1)).is_dir():
            bad.append((page.name, match.group(1)))
    return bad


def main() -> int:
    pages = len(list(DOCS.glob("*.mdx")))
    if not pages:
        print(f"FAIL: no docs pages found under {DOCS}.")
        return 1

    bad = check_skill_names(DOCS, SKILLS)
    if not bad:
        print(f"OK: all {pages} skills-reference pages name a skill that exists.")
        return 0

    print(f"FAIL: {len(bad)} skills-reference page(s) with a bad skill name.\n")
    for page, claimed in bad:
        if claimed:
            print(f"  {page}: names `{claimed}`, which is not a directory under skills/")
        else:
            print(f"  {page}: carries no `Skill: \\`infrahub-...\\`` line")
    print("\nAdd or correct the line so it matches the directory under skills/.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
