#!/usr/bin/env python3
"""Assert that this repo's routing symlinks resolve to their targets.

`.claude/rules` is what makes the path-scoped rules mechanism work, and
`.agents/` and `.codex/` are the same idea extended to agents other than
Claude Code: three relative symlinks each, pointing at `skills/`,
`.claude/skills/`, and `dev/guidelines/` so those agents find the shipped
skills, the contributor skills, and the rules without a second copy of
either. git materializes a symlink as a regular text file when
`core.symlinks` is false, and every agent then silently loads nothing from
that path — no error, no failing job, just guidance that stops arriving.
This is the check that turns that into a red build.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (link, target) pairs, every one relative to ROOT.
LINKS = (
    (ROOT / ".claude" / "rules", ROOT / "dev" / "guidelines"),
    (ROOT / ".agents" / "skills", ROOT / "skills"),
    (ROOT / ".agents" / "contributor-skills", ROOT / ".claude" / "skills"),
    (ROOT / ".agents" / "rules", ROOT / "dev" / "guidelines"),
    (ROOT / ".codex" / "skills", ROOT / "skills"),
    (ROOT / ".codex" / "contributor-skills", ROOT / ".claude" / "skills"),
    (ROOT / ".codex" / "rules", ROOT / "dev" / "guidelines"),
)

def _check(link: Path, target: Path) -> str | None:
    """Return an error message for one link, or None if it is fine."""
    rel = link.relative_to(ROOT)
    if not link.exists():
        return f"BROKEN: {rel} does not exist."
    if not link.is_dir():
        return (
            f"BROKEN: {rel} is a regular file, not a symlink.\n"
            f"    Contents: {link.read_text()[:80]!r}\n"
            "    git wrote it this way because core.symlinks is false."
        )
    if link.resolve() != target.resolve():
        return f"BROKEN: {rel} resolves to {link.resolve()},\n    expected {target}."
    return None


def main() -> int:
    errors = []
    ok = []
    for link, target in LINKS:
        error = _check(link, target)
        if error is not None:
            errors.append(error)
        else:
            rel = link.relative_to(ROOT)
            target_rel = target.relative_to(ROOT)
            ok.append(f"{rel} -> {target_rel}")

    if not errors:
        print(f"OK: all {len(LINKS)} routing symlinks resolve:")
        for line in ok:
            print(f"  {line}")
        return 0

    for error in errors:
        print(error)

    print(
        "\n  No skills or rules load through a broken link. Repair with:\n"
        "    git config core.symlinks true && git checkout -- .claude .agents .codex\n"
        "  or recreate the missing ones:\n"
        "    rm -f .claude/rules && ln -s ../dev/guidelines .claude/rules\n"
        "    rm -f .agents/skills && ln -s ../skills .agents/skills\n"
        "    rm -f .agents/contributor-skills && ln -s ../.claude/skills .agents/contributor-skills\n"
        "    rm -f .agents/rules && ln -s ../dev/guidelines .agents/rules\n"
        "    rm -f .codex/skills && ln -s ../skills .codex/skills\n"
        "    rm -f .codex/contributor-skills && ln -s ../.claude/skills .codex/contributor-skills\n"
        "    rm -f .codex/rules && ln -s ../dev/guidelines .codex/rules"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
