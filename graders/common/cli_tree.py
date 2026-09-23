"""The `infrahubctl` command tree, and the scanner that finds invocations.

This module is the single source of truth for both consumers:

- ``scripts/check-cli-invocations.py`` checks what the *repository* prints.
- ``graders/common/lib.py`` checks what the *model* prints.

They ask the same question of different text, so they were originally two
copies of the same tree with a comment asking future maintainers to keep
them in step. A comment is not a coupling: the copy the graders use is the
one that decides whether an eval passes, so a CLI change applied to the
script alone would pass CI and leave the evals grading a stale tree.

It lives under ``graders/`` rather than ``scripts/`` because a grader has to
import it as a plain sibling module — the eval harness puts the grader's own
directory on ``sys.path`` and nothing else. The script, which runs from a
checkout, loads it by path.

The tree is transcribed from the SDK's Typer registrations
(``infrahub_sdk/ctl/``). Update ``SDK_VERSION`` and the tree together, and
say in the commit which SDK version the tree was read from.
"""

from __future__ import annotations

import re

SDK_VERSION = "1.23.1"

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
# `infrahubctl check run <name>` reads fine and silently looks for a check  # cli-check: ignore infrahubctl check run
# literally named "run".
SUSPICIOUS_VERBS: set[str] = {
    "run", "list", "get", "create", "delete", "load", "dump",
    "check", "validate", "execute", "show", "new", "add", "export", "import",
}

# Words that follow `infrahubctl` in a heading or a table cell without being
# a command.
PROSE_ALLOWLIST: set[str] = {"available", "commands", "first"}

# Words that read as a command: every subcommand registered anywhere in the
# tree, every top-level command, and the generic verbs above. Used only by
# the bare `group sub` scan, where nothing else says the span is a command.
COMMAND_WORDS: set[str] = (
    SUSPICIOUS_VERBS
    | LEAVES
    | {sub for subs in GROUPS.values() for sub in subs}
)

# `_` belongs in the token class: transform and generator names are snake
# case, and without it `infrahubctl generator create_dc` truncates to the
# verb `create` and trips the suspicious-verb rule.
TOKEN = r"[a-z][a-z0-9_-]*"

# `infrahubctl` followed by a word. Captures up to two further tokens so a
# group can be validated against its subcommand and a leaf against a verb.
#
# The command token must follow `infrahubctl` directly. Skipping leading
# flags would make `infrahubctl --version, or check ...` parse as the
# command `check`, turning prose into a false positive. A global flag before
# the command is rare enough in docs that a missed check beats a false one.
INVOCATION = re.compile(rf"infrahubctl[ \t]+({TOKEN})(?:[ \t]+({TOKEN}))?")

# Bare `infrahubctl`-less `group sub` inside a code span, for prose that
# drops the binary name: "`infrahubctl schema load`, then `schema validate`".  # cli-check: ignore schema validate
#
# The span has to open with `group sub`, and — with no `infrahubctl` here to
# say the span is a command at all — the second token has to read as one.
# Anchoring alone does not separate an invocation from an ordinary Infrahub
# noun phrase, because those open with the group word too: "the `schema      # cli-check: ignore
# files` in the repository", "the `object kinds` you model", "a `branch      # cli-check: ignore
# strategy`" all start at position zero, and a gate that blocks merges on
# normal prose gets disabled rather than fixed. Requiring a command word in
# the subcommand slot keeps the case this exists for — `validate` is one,
# `files` and `kinds` and `strategy` are not — at the cost of missing a
# wrong subcommand that happens to be a noun, which is the direction the
# rest of this module already errs in.
BARE_GROUP = re.compile(
    r"^(" + "|".join(sorted(GROUPS)) + rf")[ \t]+({TOKEN})(?:[ \t]|$)"
)

FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
SPAN = re.compile(r"`([^`\n]+)`")
_SHELL_COMMENT = re.compile(r"^\s*#.*$", re.MULTILINE)

# The one legitimate reason to print a command that does not exist is to
# tell the reader it does not exist. Put the marker on the same line, in
# whatever comment syntax the file uses (an HTML comment in markdown, a
# `#` comment in Python), followed by the invocation it silences, written
# however it reads naturally in the prose (arguments included, since a
# release note names a command the way it was actually run). The marker
# silences only that named form, compared the same way this module compares
# any two invocations: by its first two tokens after `infrahubctl` (or, for
# the bare `group sub` span, its first two tokens outright). A blanket
# `IGNORE_MARKER in line` check used to silence the whole line instead, so
# appending a second, different bad invocation to an already-marked line
# passed unnoticed. A markdown bullet is one line, so a bullet naming two
# invalid invocations needs two markers on that one line, and both are
# read, not just the first.
IGNORE_MARKER = "cli-check: ignore"


def _named_invocation(text: str) -> str:
    """Normalize one marker's free-form text to the two-token form this
    module reports invocations in.

    `invalid_invocations_in_region` never reports more than `infrahubctl`
    plus two tokens (or, for a bare span, two tokens outright); arguments
    play no part in identifying which invocation was flagged. Truncating
    the marker's text the same way is what lets a marker name the command
    the way it was actually written, arguments included, rather than the
    one bare spelling the scanner happens to report.
    """
    match = INVOCATION.match(text)
    if match:
        first, second = match.groups()
        return f"infrahubctl {first}" + (f" {second}" if second else "")
    return " ".join(text.split()[:2])


def ignored_invocations(line: str) -> set[str]:
    """Every invocation a `cli-check: ignore <invocation>` marker on this
    line names, normalized to the two-token form
    `invalid_invocations_in_region` reports invocations in.

    Splitting on the marker text, rather than a single regex search, is
    what lets more than one marker share a line: each marker's text runs up
    to the next marker or a trailing HTML-comment closer, whichever comes
    first, so a second marker never gets swallowed into the first's
    capture. Empty when the line carries no marker, or only bare ones with
    nothing after them to name: a bare marker protects nothing, rather
    than falling back to protecting the whole line.
    """
    named: set[str] = set()
    for chunk in line.split(IGNORE_MARKER)[1:]:
        text = chunk.split("-->", 1)[0].strip()
        if text:
            named.add(_named_invocation(text))
    return named


def code_regions(text: str) -> list[str]:
    """Return the parts of a document that read as shell input.

    Prose that happens to follow the word `infrahubctl` ("infrahubctl reads
    the token from the environment") is not an invocation, so only fenced
    blocks and inline code spans are scanned.

    Regions are returned as a list rather than one joined string because
    joining welds unrelated spans into commands that were never written:
    "The `infrahubctl` CLI ... name the transform `spine_config`" becomes
    the invocation `infrahubctl spine_config`. Callers scan each region.  # cli-check: ignore infrahubctl spine_config

    Shell comment lines inside a fence are stripped for the same reason —
    they are prose, and this repository's own rules annotate fences that
    way.
    """
    regions = [_SHELL_COMMENT.sub("", block) for block in FENCE.findall(text)]
    regions.extend(SPAN.findall(FENCE.sub("\n", text)))
    return [region for region in regions if region.strip()]


def invalid_invocations_in_region(region: str, *, spans_only: bool = True) -> list[str]:
    """Return every `infrahubctl ...` form in one code region that does not exist.

    ``spans_only`` says whether the region came from an inline code span. The
    bare `group sub` form only makes sense there — inside a fence, a line
    that opens with `schema` is not an invocation with the binary name
    dropped, it is a line of something else.
    """
    bad: list[str] = []
    for first, second in INVOCATION.findall(region):
        if first in PROSE_ALLOWLIST:
            continue
        shown = f"infrahubctl {first}" + (f" {second}" if second else "")
        if first in GROUPS:
            # A bare group name is fine in prose ("the `infrahubctl schema`
            # commands"); only a wrong subcommand is a defect.
            if second and second not in GROUPS[first]:
                bad.append(shown)
        elif first in LEAVES:
            if second in SUSPICIOUS_VERBS:
                bad.append(shown)
        else:
            bad.append(shown)
    if spans_only:
        for group, sub in BARE_GROUP.findall(region.strip()):
            if sub in COMMAND_WORDS and sub not in GROUPS[group]:
                bad.append(f"{group} {sub}")
    return bad


def invalid_invocations(text: str) -> list[str]:
    """Return every `infrahubctl ...` form in a whole document that does not exist.

    Only code regions are scanned, and each is scanned separately.
    """
    return [
        shown
        for region in code_regions(text)
        for shown in invalid_invocations_in_region(region)
    ]


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
        return (
            f"`{first}` takes its target as a positional argument: "
            f"infrahubctl {first} <name>"
        )
    if first in SUSPICIOUS_VERBS and first not in LEAVES:
        for group, subs in GROUPS.items():
            if first in subs:
                return f"did you mean `infrahubctl {group} {first}`?"
    return "not a registered command; see --list"
