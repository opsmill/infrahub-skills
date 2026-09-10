#!/usr/bin/env python3
"""Check every `infrahubctl ...` invocation printed anywhere in this repo.

A skill that prints a command which does not exist costs a reader a failed
run and, worse, teaches them the command is unavailable. Two such defects
were reported independently (`infrahubctl schema validate`,
`infrahubctl menu check`), which is what motivated a sweep rather than two
point fixes; the sweep then found four more nobody had reported.

The sweep covers more than `skills/`. A grader that rewards an invented
command, or an eval rubric that asks for one, undoes the prose fix in the
layer that scores it: `graders/managing-transforms/lib.py` was accepting
`infrahubctl check run` as a passing signal while the rule teaching it was
being deleted. So `graders/`, `tests/`, `dev/` and `eval.yaml` are scanned
too.

The command tree lives in `graders/common/cli_tree.py`, which is the one
place it is written down. See that module for why.

Usage::

    python scripts/check-cli-invocations.py            # check, exit 1 on failure
    python scripts/check-cli-invocations.py --list     # print the known tree
"""

from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_TREE_PATH = ROOT / "graders" / "common" / "cli_tree.py"
_spec = importlib.util.spec_from_file_location("infrahubctl_cli_tree", _TREE_PATH)
cli_tree = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli_tree)

SDK_VERSION = cli_tree.SDK_VERSION
IGNORE_MARKER = cli_tree.IGNORE_MARKER

# Every tree that can print or grade a command.
# `dev/specs/` is deliberately absent: those are historical design records,
# and rewriting a record of what was proposed at the time is not a fix.
SCAN_TARGETS = (
    "skills", "graders", "tests", "eval.yaml",
    "dev/guides", "dev/knowledges", "dev/commands",
)
SCAN_SUFFIXES = {".md", ".py", ".yaml", ".yml"}

# Files where a ``` fence opens a block of shell input. Markdown obviously;
# eval.yaml because its instruction blocks are markdown inside a YAML block
# scalar.
FENCED_SUFFIXES = {".md", ".yaml", ".yml"}
SELF = Path(__file__).resolve()


def _files() -> list[Path]:
    out: list[Path] = []
    for target in SCAN_TARGETS:
        path = ROOT / target
        if path.is_file():
            out.append(path)
        elif path.is_dir():
            out.extend(
                p for p in path.rglob("*")
                if p.is_file() and p.suffix in SCAN_SUFFIXES and p.resolve() != SELF
            )
    return sorted(out)


def _scannable(line: str, in_fence: bool) -> list[str]:
    """The parts of one line that read as shell input.

    Outside a fence that means backtick spans only, in every file type. A
    Python comment, a YAML rubric sentence and a markdown paragraph are all
    prose, and prose that happens to contain the word `infrahubctl` ("no
    infrahubctl command covers this") is not an invocation. A command that
    is being *taught* is written in backticks or a fence; one that is not
    is not being taught.
    """
    if in_fence:
        # A `#` comment inside a fence is prose, and this repository's own
        # rules annotate fences that way.
        return [] if line.lstrip().startswith("#") else [line]
    return cli_tree.code_regions(line)


def scan() -> dict[str, list[tuple[str, int, str]]]:
    bad: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        in_fence = False
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if path.suffix in FENCED_SUFFIXES and line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if IGNORE_MARKER in line:
                continue
            for region in _scannable(line, in_fence):
                for shown in cli_tree.invalid_invocations_in_region(
                    region, spans_only=not in_fence
                ):
                    bad[shown].append((rel, lineno, line.strip()))

    return bad


def main() -> int:
    if "--list" in sys.argv:
        print(cli_tree.known_tree())
        return 0

    bad = scan()
    scanned = ", ".join(SCAN_TARGETS)
    if not bad:
        print(f"OK: every infrahubctl invocation in {scanned} exists (SDK {SDK_VERSION}).")
        return 0

    total = sum(len(v) for v in bad.values())
    print(f"FAIL: {total} invalid infrahubctl invocation(s) across {len(bad)} form(s).\n")
    for shown, hits in sorted(bad.items()):
        print(f"  {shown}")
        parts = (shown.replace("infrahubctl ", "").split() + [None])[:2]
        print(f"    {cli_tree.suggest(*parts)}")
        for rel, lineno, text in hits:
            print(f"    {rel}:{lineno}")
            print(f"      {text[:110]}")
        print()
    print(
        "Fix the invocation, or update the tree in graders/common/cli_tree.py "
        "if the CLI changed."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
