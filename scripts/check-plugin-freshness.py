#!/usr/bin/env python3
"""Compare the installed Infrahub plugin against this working tree.

Invoking a skill in this repository runs the *installed* plugin, not the
files you just edited. This prints how far apart the two are so an edit
is never mistaken for a passing test.

Exit 0 when they match or the plugin is not installed, 1 when they differ.
"""

from __future__ import annotations

import filecmp
import sys
from pathlib import Path

REPO_SKILLS = Path(__file__).resolve().parent.parent / "skills"
CACHE_GLOB = "plugins/cache/*/infrahub/*/skills"


def installed_skill_dirs() -> list[Path]:
    return sorted(p for p in Path.home().joinpath(".claude").glob(CACHE_GLOB) if p.is_dir())


def compare(installed: Path) -> tuple[int, int]:
    """Return (differing files, files present in only one tree)."""
    differing = only = 0
    repo_files = {p.relative_to(REPO_SKILLS) for p in REPO_SKILLS.rglob("*") if p.is_file()}
    cache_files = {p.relative_to(installed) for p in installed.rglob("*") if p.is_file()}
    only = len(repo_files ^ cache_files)
    for rel in sorted(repo_files & cache_files):
        if not filecmp.cmp(REPO_SKILLS / rel, installed / rel, shallow=False):
            differing += 1
    return differing, only


def main() -> int:
    if not REPO_SKILLS.is_dir():
        print("No skills/ directory — run this from the repository root.")
        return 0

    dirs = installed_skill_dirs()
    if not dirs:
        print(
            "Infrahub plugin not installed. Skills invoked here resolve to "
            "nothing, so read skills/<name>/SKILL.md directly or run evals."
        )
        return 0

    stale = False
    for installed in dirs:
        version = installed.parent.name
        differing, only = compare(installed)
        if differing or only:
            stale = True
            print(
                f"STALE: installed plugin {version} differs from this tree "
                f"({differing} file(s) changed, {only} added or removed).\n"
                f"  installed: {installed}\n"
                f"  Invoking a skill here runs that copy, not your edit.\n"
                f"  Verify through evals (skillgrade) or by reading the "
                f"working-tree SKILL.md."
            )
        else:
            print(f"OK: installed plugin {version} matches this tree.")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
