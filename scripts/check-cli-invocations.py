#!/usr/bin/env python3
"""Check every `infrahubctl ...` and `gh search --state` invocation printed in this repo.

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

It also checks one `gh` surface: the `--state` value on `gh search issues`
and `gh search prs`, which accept only `open` or `closed`. Two skills printed
`--state all` for their duplicate search, so the step returned usage text
instead of results (#136). No other `gh` flag is checked.

Usage::

    python scripts/check-cli-invocations.py            # check, exit 1 on failure
    python scripts/check-cli-invocations.py --list     # print the known tree
"""

from __future__ import annotations

import importlib.util
import re
import shlex
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
    "dev/README.md", ".agents/skills", "docs/docs",
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


def _walk(lines: list[str], suffix: str):
    """Yield (lineno, line, in_fence) per line; in_fence is None on a fence
    marker line.

    A fence only closes on a run of backticks at least as long as the one
    that opened it — the CommonMark rule. Toggling on any run of three or
    more instead flips the tracked state on a nested fence's own marker
    line, so a ```yaml block inside a four-backtick markdown block (how
    `anatomy-of-a-skill.mdx` shows a rule's own fenced examples) reads as
    prose rather than shell input from that point on.
    """
    fence_len = 0
    for lineno, line in enumerate(lines, 1):
        if suffix in FENCED_SUFFIXES:
            run = _fence_marker(line)
            if fence_len:
                # A shorter run does not close the fence, and per CommonMark
                # is literal content of it — not a marker line to skip.
                if run >= fence_len:
                    fence_len = 0
                    yield lineno, line, None
                    continue
            elif run:
                fence_len = run
                yield lineno, line, None
                continue
        yield lineno, line, fence_len > 0


def _bad_in_lines(lines: list[str], suffix: str) -> list[tuple[int, str, str]]:
    """Bad invocations in one file's lines, as (lineno, shown form, line text)."""
    bad: list[tuple[int, str, str]] = []
    for lineno, line, in_fence in _walk(lines, suffix):
        if in_fence is None:
            continue
        ignored = cli_tree.ignored_invocations(line)
        for region in _scannable(line, in_fence):
            for shown in cli_tree.invalid_invocations_in_region(
                region, spans_only=not in_fence
            ):
                if shown in ignored:
                    continue
                bad.append((lineno, shown, line.strip()))
    return bad


# `gh search issues|prs` accept only these `--state` values. Keyed by
# subcommand because the value sets differ: `gh issue list` and
# `gh pr list` do accept `all`, so a flat check would flag valid commands.
GH_SEARCH_STATES: dict[str, set[str]] = {
    "issues": {"open", "closed"},
    "prs": {"open", "closed"},
}
_GH_SEARCH = re.compile(r"\bgh\s+search\s+(issues|prs)\b([^|;&]*)")
# A span may wrap across lines inside one paragraph, as markdown allows.
_GH_SPAN = re.compile(r"`([^`]+)`")


def _gh_bad_forms(text: str) -> list[str]:
    """Every `gh search <sub> --state <value>` in `text` whose value gh
    rejects, in the form the gate reports.

    The arguments are tokenized the way a shell would, so `--state all`
    inside a quoted search query is part of the query, not an option. Text
    `shlex` cannot tokenize (an unbalanced quote in prose) falls back to a
    plain split.
    """
    forms: list[str] = []
    for cmd in _GH_SEARCH.finditer(text):
        sub = cmd.group(1)
        try:
            tokens = shlex.split(cmd.group(2))
        except ValueError:
            tokens = cmd.group(2).split()
        for i, token in enumerate(tokens):
            if token == "--state":
                value = tokens[i + 1] if i + 1 < len(tokens) else ""
            elif token.startswith("--state="):
                value = token.removeprefix("--state=")
            else:
                continue
            if value and value not in GH_SEARCH_STATES[sub]:
                forms.append(f"gh search {sub} --state {value}")
    return forms


def _gh_regions(lines: list[str], suffix: str):
    """Yield (lineno, text, source lines) for every stretch of shell input
    a `gh` command could sit in, joined across the line breaks a command
    survives. The source lines are only the ones the stretch covers, which
    is what scopes an ignore marker to its own command.

    The infrahubctl scan reads one line at a time, which misses both shapes
    #136 was filed on: a fenced command continued with `\\` onto a line
    holding the flag, and an inline code span wrapped across two lines of
    a markdown paragraph. Inside a fence this joins `\\` continuations;
    outside one it matches spans over the whole paragraph. Python sources
    keep one line per paragraph, since backticks in a docstring do not
    pair across lines the way markdown's do.
    """
    wraps = suffix in FENCED_SUFFIXES
    para: list[tuple[int, str]] = []
    cont: list[tuple[int, str]] = []

    def flush_para():
        if not para:
            return
        first = para[0][0]
        text = "\n".join(line for _, line in para)
        spans = set()
        for m in _GH_SPAN.finditer(text):
            lineno = first + text.count("\n", 0, m.start())
            spans.add((lineno, lineno + m.group(1).count("\n"), m.group(1).replace("\n", " ")))
        # One stray backtick run (an inline ```python mention) shifts the
        # paragraph-wide pairing for everything after it, so each line is
        # also paired on its own. The union keeps both wrapped spans and
        # spans the paragraph pass misaligned.
        spans |= {
            (lineno, lineno, m.group(1)) for lineno, line in para for m in _GH_SPAN.finditer(line)
        }
        for start, stop, span in sorted(spans):
            yield start, span, [line for n, line in para if start <= n <= stop]
        para.clear()

    def flush_cont():
        if not cont:
            return
        # A shell drops the backslash-newline outright, so `--state=\` then
        # `all` reads as `--state=all`; spaces before the backslash stay.
        text = "".join(line.rstrip().removesuffix("\\") for _, line in cont)
        yield cont[0][0], text, [line for _, line in cont]
        cont.clear()

    for lineno, line, in_fence in _walk(lines, suffix):
        if in_fence:
            yield from flush_para()
            if line.lstrip().startswith("#") and not cont:
                continue
            cont.append((lineno, line))
            if line.rstrip().endswith("\\"):
                continue
            yield from flush_cont()
            continue
        yield from flush_cont()
        if in_fence is None or not line.strip():
            yield from flush_para()
            continue
        para.append((lineno, line))
        if not wraps:
            yield from flush_para()
    yield from flush_cont()
    yield from flush_para()


def _gh_ignored(source: list[str]) -> set[str]:
    """Forms a `cli-check: ignore <invocation>` marker names on the lines a
    region covers.

    The marker text goes through the same parser as the command, so it can
    name the invocation as written, arguments included, or in the short
    form the gate reports. Both reduce to the same form.
    """
    named: set[str] = set()
    for line in source:
        for chunk in line.split(cli_tree.IGNORE_MARKER)[1:]:
            named.update(_gh_bad_forms(chunk.split("-->", 1)[0]))
    return named


def _bad_gh_in_lines(lines: list[str], suffix: str) -> list[tuple[int, str, str]]:
    """`gh search` invocations with a `--state` value gh rejects, as
    (lineno, shown form, line text)."""
    bad: list[tuple[int, str, str]] = []
    for lineno, text, source in _gh_regions(lines, suffix):
        ignored = _gh_ignored(source)
        for shown in _gh_bad_forms(text):
            if shown not in ignored:
                bad.append((lineno, shown, lines[lineno - 1].strip()))
    return bad


def scan() -> dict[str, list[tuple[str, int, str]]]:
    bad: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, shown, text in _bad_in_lines(lines, path.suffix):
            bad[shown].append((rel, lineno, text))
        for lineno, shown, text in _bad_gh_in_lines(lines, path.suffix):
            bad[shown].append((rel, lineno, text))

    return bad


def main() -> int:
    if "--list" in sys.argv:
        print(cli_tree.known_tree())
        return 0

    bad = scan()
    scanned = ", ".join(SCAN_TARGETS)
    if not bad:
        print(
            f"OK: every infrahubctl invocation in {scanned} exists (SDK {SDK_VERSION}), "
            "and every gh search --state value is valid."
        )
        return 0

    total = sum(len(v) for v in bad.values())
    print(f"FAIL: {total} invalid CLI invocation(s) across {len(bad)} form(s).\n")
    for shown, hits in sorted(bad.items()):
        print(f"  {shown}")
        if shown.startswith("gh "):
            print("    gh search accepts --state open or closed; omit --state to search both.")
        else:
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
