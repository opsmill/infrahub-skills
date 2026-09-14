#!/usr/bin/env python3
"""Assert that `.claude/rules` resolves to the canonical rules directory.

The whole path-scoped rules mechanism hangs off this one symlink. git
materializes a symlink as a regular text file when `core.symlinks` is false,
and every agent then silently loads no rules at all — no error, no failing
job, just guidance that stops arriving. This is the check that turns that
into a red build.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = ROOT / ".claude" / "rules"
TARGET = ROOT / "dev" / "guidelines"


def main() -> int:
    if not LINK.exists():
        print(f"BROKEN: {LINK.relative_to(ROOT)} does not exist.")
    elif not LINK.is_dir():
        print(
            f"BROKEN: {LINK.relative_to(ROOT)} is a regular file, not a symlink.\n"
            f"  Contents: {LINK.read_text()[:80]!r}\n"
            "  git wrote it this way because core.symlinks is false."
        )
    elif LINK.resolve() != TARGET.resolve():
        print(
            f"BROKEN: {LINK.relative_to(ROOT)} resolves to {LINK.resolve()},\n"
            f"  expected {TARGET}."
        )
    else:
        rules = sorted(p.name for p in LINK.glob("*.md"))
        print(f"OK: .claude/rules -> dev/guidelines ({len(rules)} rules: {', '.join(rules)})")
        return 0

    print(
        "\n  No rules load in this state. Repair with:\n"
        "    git config core.symlinks true && git checkout -- .claude/rules\n"
        "  or recreate it:\n"
        "    rm -f .claude/rules && ln -s ../dev/guidelines .claude/rules"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
