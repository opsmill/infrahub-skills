#!/usr/bin/env python3
"""Check every `infrahubctl ...` invocation printed in the skills tree.

A skill that prints a command which does not exist costs a reader a failed
run and, worse, teaches them the command is unavailable. Two such defects
were reported independently (`infrahubctl schema validate`,
`infrahubctl menu check`), which is what motivated a sweep rather than two
point fixes; the sweep then found four more nobody had reported.

The command tree below is transcribed from the SDK's Typer registrations
(``infrahub_sdk/ctl/``). Update ``SDK_VERSION`` and the tree together when
the CLI gains or renames a command, and say in the commit which SDK version
the tree was read from.

Usage::

    python scripts/check-cli-invocations.py            # check, exit 1 on failure
    python scripts/check-cli-invocations.py --list     # print the known tree
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

SDK_VERSION = "1.23.1"

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

# Sub-apps registered with `app.add_typer(..., name=...)`, and their commands.
GROUPS: dict[str, set[str]] = {
    "branch": {"create", "delete", "list", "merge", "rebase", "report", "validate"},
    "graphql": {"export-schema", "generate-return-types", "query-report"},
    "marketplace": {"get", "list", "search", "show"},
    "menu": {"load", "validate"},
    "object": {"create", "delete", "get", "load", "update", "validate"},
    "repository": {"add", "init", "list"},
    "schema": {"check", "export", "format", "list", "load", "show"},
    "task": {"list"},
    "telemetry": {"export", "list"},
    "validate": {"graphql-query", "schema"},
}

# Top-level commands registered directly on the root app.
LEAVES: set[str] = {
    "check", "dump", "generator", "info", "load",
    "protocols", "render", "run", "transform", "version",
}

# A leaf command takes its target as a positional argument, so the token
# after it is a user-chosen name we cannot validate. What we can catch is a
# generic verb sitting there, which is nearly always an invented subcommand:
# `infrahubctl check run <name>` reads fine and silently looks for a check
# literally named "run".
SUSPICIOUS_VERBS: set[str] = {
    "run", "list", "get", "create", "delete", "load", "dump",
    "check", "validate", "execute", "show", "new", "add", "export", "import",
}

# `infrahubctl` followed by a word. Captures up to two further tokens so a
# group can be validated against its subcommand and a leaf against a verb.
#
# The command token must follow `infrahubctl` directly. Skipping leading
# flags would make `infrahubctl --version, or check ...` parse as the
# command `check`, turning prose into a false positive. A global flag before
# the command is rare enough in docs that a missed check beats a false one.
#
# `_` belongs in the token class: transform and generator names are snake
# case, and without it `infrahubctl generator create_dc` truncates to the
# verb `create` and trips the suspicious-verb rule.
TOKEN = r"[a-z][a-z0-9_-]*"
INVOCATION = re.compile(rf"infrahubctl\s+({TOKEN})(?:\s+({TOKEN}))?")

# Bare `group sub` inside backticks, for prose that drops the binary name,
# e.g. "`infrahubctl schema load`, `schema validate`".
BARE_GROUP = re.compile(r"`(" + "|".join(GROUPS) + rf")\s+({TOKEN})")

# Prose that reads like an invocation but is not one, e.g.
# "## Fetching (infrahubctl first)" or a rules table cell.
PROSE_ALLOWLIST: set[str] = {"available", "commands", "first"}

# Escape hatch for the one legitimate reason to print a command that does
# not exist: telling the reader it does not exist. Put the marker on the
# same line as the mention.
IGNORE_MARKER = "<!-- cli-check: ignore -->"


def known_tree() -> str:
    lines = [f"infrahubctl command tree (SDK {SDK_VERSION})", ""]
    lines.append("top level: " + " ".join(sorted(LEAVES)))
    lines.append("")
    for group, subs in sorted(GROUPS.items()):
        lines.append(f"{group:12s}: {' '.join(sorted(subs))}")
    return "\n".join(lines)


def suggest(first: str, second: str | None) -> str:
    """Best-effort hint for a rejected invocation."""
    if first in GROUPS and second:
        return f"`{first}` accepts: {', '.join(sorted(GROUPS[first]))}"
    if first in LEAVES and second in SUSPICIOUS_VERBS:
        return f"`{first}` takes its target as a positional argument: infrahubctl {first} <name>"
    if first in SUSPICIOUS_VERBS and first not in LEAVES:
        for group, subs in GROUPS.items():
            if first in subs:
                return f"did you mean `infrahubctl {group} {first}`?"
    return "not a registered command; see --list"


def scan() -> dict[str, list[tuple[str, int, str]]]:
    bad: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    for path in sorted(SKILLS.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if IGNORE_MARKER in line:
                continue
            for first, second in INVOCATION.findall(line):
                if first in PROSE_ALLOWLIST:
                    continue
                shown = f"infrahubctl {first}" + (f" {second}" if second else "")
                if first in GROUPS:
                    # A bare group name is fine in prose ("the `infrahubctl schema`
                    # commands"); only a wrong subcommand is a defect.
                    if second and second not in GROUPS[first]:
                        bad[shown].append((rel, lineno, line.strip()))
                elif first in LEAVES:
                    if second in SUSPICIOUS_VERBS:
                        bad[shown].append((rel, lineno, line.strip()))
                else:
                    bad[shown].append((rel, lineno, line.strip()))

            for group, sub in BARE_GROUP.findall(line):
                if sub not in GROUPS[group]:
                    shown = f"{group} {sub}"
                    if (rel, lineno, line.strip()) not in bad.get(f"infrahubctl {shown}", []):
                        bad[shown].append((rel, lineno, line.strip()))

    return bad


def main() -> int:
    if "--list" in sys.argv:
        print(known_tree())
        return 0

    bad = scan()
    if not bad:
        print(f"OK: every infrahubctl invocation in skills/ exists (SDK {SDK_VERSION}).")
        return 0

    total = sum(len(v) for v in bad.values())
    print(f"FAIL: {total} invalid infrahubctl invocation(s) across {len(bad)} form(s).\n")
    for shown, hits in sorted(bad.items()):
        print(f"  {shown}")
        print(f"    {suggest(*(shown.replace('infrahubctl ', '').split() + [None])[:2])}")
        for rel, lineno, text in hits:
            print(f"    {rel}:{lineno}")
            print(f"      {text[:110]}")
        print()
    print("Fix the invocation, or update the tree in this script if the CLI changed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
