#!/usr/bin/env python3
"""Compare the installed Infrahub plugin against this working tree.

Invoking a skill in this repository runs the *installed* plugin, not the
files you just edited. This prints how far apart the two are so an edit
is never mistaken for a passing test.

Exit 0 when they match or the plugin is not installed, 1 when they differ.
"""

from __future__ import annotations

import filecmp
import subprocess
import sys
from pathlib import Path

REPO_SKILLS = Path(__file__).resolve().parent.parent / "skills"
CACHE_GLOB = "plugins/cache/*/infrahub/*/skills"


def installed_skill_dirs() -> list[Path]:
    return sorted(p for p in Path.home().joinpath(".claude").glob(CACHE_GLOB) if p.is_dir())


def _tracked(root: Path) -> set[Path]:
    """Skill files, minus what a test run or the OS leaves behind.

    `invoke test` writes __pycache__ under skills/; counting those as drift
    tells a contributor their edit is untested when it is not.
    """
    out = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        if rel.suffix in {".pyc", ".pyo"}:
            continue
        out.add(rel)
    return out


def compare(installed: Path) -> tuple[int, int]:
    """Return (differing files, files present in only one tree)."""
    differing = 0
    repo_files = _tracked(REPO_SKILLS)
    cache_files = _tracked(installed)
    only = len(repo_files ^ cache_files)
    for rel in sorted(repo_files & cache_files):
        if not filecmp.cmp(REPO_SKILLS / rel, installed / rel, shallow=False):
            differing += 1
    return differing, only


def check_rules_symlink() -> bool:
    """Delegate to the standalone guard so CI and this share one implementation."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "check-symlinks.py")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout.strip())
    return result.returncode == 0


def main() -> int:
    if not REPO_SKILLS.is_dir():
        print("No skills/ directory — run this from the repository root.")
        return 0

    broken = not check_rules_symlink()

    dirs = installed_skill_dirs()
    if not dirs:
        print(
            "Infrahub plugin not installed. Skills invoked here resolve to "
            "nothing, so read skills/<name>/SKILL.md directly or run evals."
        )
        return 1 if broken else 0

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
    return 1 if (stale or broken) else 0


if __name__ == "__main__":
    sys.exit(main())
