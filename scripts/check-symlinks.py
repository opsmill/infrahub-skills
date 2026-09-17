#!/usr/bin/env python3
"""Assert that this repo's routing symlinks resolve to their targets.

`.agents/` is the source of truth for everything this repo authors for its
own agents: `.agents/skills/` holds the contributor skills and
`.agents/rules` points at `dev/guidelines/`. `.claude/` and `.codex/` are
adapters — they hold nothing but relative symlinks into `.agents/`, so each
agent finds the same content under the path it already looks in, with no
second copy and no adapter owning the originals.

`skills/` at the repo root is deliberately outside this scheme. It is the
product: the skills the plugin ships, which `plugin.json` exposes and the
eval suite reads directly. No agent working *on* this repo needs to invoke
them, so nothing routes to them.

git materializes a symlink as a regular text file when `core.symlinks` is
false, and every agent then silently loads nothing from that path: no
error, no failing job, just guidance that stops arriving. This is the
check that turns that into a red build.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (link, target) pairs, every one relative to ROOT.
LINKS = (
    (ROOT / ".claude" / "rules", ROOT / "dev" / "guidelines"),
    (ROOT / ".claude" / "skills", ROOT / ".agents" / "skills"),
    (ROOT / ".agents" / "rules", ROOT / "dev" / "guidelines"),
    (ROOT / ".codex" / "skills", ROOT / ".agents" / "skills"),
    (ROOT / ".codex" / "rules", ROOT / "dev" / "guidelines"),
)

# The link targets that must be real directories. Every link above resolves
# through one of these; turning either into a link of its own makes a cycle
# that resolves to nothing.
REAL_DIRS = (ROOT / ".agents" / "skills", ROOT / "dev" / "guidelines")


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


def _check_real(path: Path) -> str | None:
    """Return an error message if a link target is missing or itself a link."""
    rel = path.relative_to(ROOT)
    if path.is_symlink():
        return (
            f"BROKEN: {rel} is a symlink. It has to be the real directory —\n"
            "    the routing links resolve through it, so a link here is a cycle."
        )
    if not path.is_dir():
        return f"BROKEN: {rel} does not exist, so every link into it dangles."
    return None


def main() -> int:
    errors = []
    ok = []

    for path in REAL_DIRS:
        error = _check_real(path)
        if error is not None:
            errors.append(error)

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
        "    rm -f .claude/skills && ln -s ../.agents/skills .claude/skills\n"
        "    rm -f .agents/rules && ln -s ../dev/guidelines .agents/rules\n"
        "    rm -f .codex/skills && ln -s ../.agents/skills .codex/skills\n"
        "    rm -f .codex/rules && ln -s ../dev/guidelines .codex/rules"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
