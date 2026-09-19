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

# Every tree that can print or grade a command.
# `dev/specs/` is deliberately absent: those are historical design records,
# and rewriting a record of what was proposed at the time is not a fix.
#
# `docs/docs` is present on purpose: it is the published documentation site,
# a reader copies commands straight out of it, and `first-schema.mdx` exists
# specifically to be followed command by command. That includes
# `docs/docs/release-notes/`, which documents what shipped in past versions
# and is a historical record in the same sense as `dev/specs/`, since a later
# SDK can remove a command a release note mentions. It is not excluded,
# because unlike `dev/specs/` it is expected to keep passing: the fix for a
# release note that no longer matches the current SDK is the `IGNORE_MARKER`
# comment on that line (`<!-- cli-check: ignore -->`), not rewriting the note
# or dropping the directory from the scan.
SCAN_TARGETS = (
    "skills", "graders", "tests", "eval.yaml",
    "dev/guides", "dev/knowledges", "dev/commands", "dev/guidelines",
    "dev/README.md", ".claude/skills", "docs/docs",
)
# `.mdx` is required for `docs/docs` to mean anything: every page in that
# tree is `.mdx` (Docusaurus's Markdown-plus-JSX format), not `.md`. Without
# it here, `docs/docs` in SCAN_TARGETS above scans zero files, so the checker
# passes on an unscanned directory rather than a clean one. That silent gap
# is exactly how four wrong `infrahubctl` commands reached the published
# skills-reference pages unnoticed: nothing ever scanned the file type they
# lived in.
SCAN_SUFFIXES = {".md", ".mdx", ".py", ".yaml", ".yml"}

# Files where a ``` fence opens a block of shell input. Markdown obviously,
# and `.mdx` is markdown for this purpose too; eval.yaml because its
# instruction blocks are markdown inside a YAML block scalar.
FENCED_SUFFIXES = {".md", ".mdx", ".yaml", ".yml"}
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


def _fence_marker(line: str) -> int:
    """The backtick-run length that opens or closes a fence on this line.

    Zero when the line, once indentation is stripped, does not start with
    three or more backticks.
    """
    stripped = line.lstrip()
    run = len(stripped) - len(stripped.lstrip("`"))
    return run if run >= 3 else 0


def _bad_in_lines(lines: list[str], suffix: str) -> list[tuple[int, str, str]]:
    """Bad invocations in one file's lines, as (lineno, shown form, line text).

    A fence only closes on a run of backticks at least as long as the one
    that opened it — the CommonMark rule. Toggling on any run of three or
    more instead flips the tracked state on a nested fence's own marker
    line, so a ```yaml block inside a four-backtick markdown block (how
    `anatomy-of-a-skill.mdx` shows a rule's own fenced examples) reads as
    prose rather than shell input from that point on.
    """
    bad: list[tuple[int, str, str]] = []
    fence_len = 0
    for lineno, line in enumerate(lines, 1):
        if suffix in FENCED_SUFFIXES:
            run = _fence_marker(line)
            if fence_len:
                # A shorter run does not close the fence, and per CommonMark
                # is literal content of it — not a marker line to skip.
                if run >= fence_len:
                    fence_len = 0
                    continue
            elif run:
                fence_len = run
                continue
        in_fence = fence_len > 0
        ignored = cli_tree.ignored_invocation(line)
        for region in _scannable(line, in_fence):
            for shown in cli_tree.invalid_invocations_in_region(
                region, spans_only=not in_fence
            ):
                if shown == ignored:
                    continue
                bad.append((lineno, shown, line.strip()))
    return bad


def scan() -> dict[str, list[tuple[str, int, str]]]:
    bad: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, shown, text in _bad_in_lines(lines, path.suffix):
            bad[shown].append((rel, lineno, text))

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
