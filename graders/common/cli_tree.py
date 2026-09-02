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
# `infrahubctl check run <name>` reads fine and silently looks for a check  # cli-check: ignore
# literally named "run".
SUSPICIOUS_VERBS: set[str] = {
    "run", "list", "get", "create", "delete", "load", "dump",
    "check", "validate", "execute", "show", "new", "add", "export", "import",
}

# Words that follow `infrahubctl` in a heading or a table cell without being
# a command.
PROSE_ALLOWLIST: set[str] = {"available", "commands", "first"}

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
# drops the binary name: "`infrahubctl schema load`, then `schema validate`".  # cli-check: ignore
#
# The span has to be exactly `group sub`, optionally with arguments after it.
# Matching a group name plus any following word anywhere in a span turns
# ordinary Infrahub nouns into build failures — "the `schema files` in the  # cli-check: ignore
# repository", "the `object kinds` you model", "a `branch strategy`" — and a  # cli-check: ignore
# gate that blocks merges on normal prose gets disabled rather than fixed.
BARE_GROUP = re.compile(
    r"^(" + "|".join(sorted(GROUPS)) + rf")[ \t]+({TOKEN})(?:[ \t]|$)"
)

FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
SPAN = re.compile(r"`([^`\n]+)`")
_SHELL_COMMENT = re.compile(r"^\s*#.*$", re.MULTILINE)

# The one legitimate reason to print a command that does not exist is to
# tell the reader it does not exist. Put the marker on the same line, in
# whatever comment syntax the file uses: `<!-- cli-check: ignore -->` in
# markdown, `# cli-check: ignore` in Python.
IGNORE_MARKER = "cli-check: ignore"


def code_regions(text: str) -> list[str]:
    """Return the parts of a document that read as shell input.

    Prose that happens to follow the word `infrahubctl` ("infrahubctl reads
    the token from the environment") is not an invocation, so only fenced
    blocks and inline code spans are scanned.

    Regions are returned as a list rather than one joined string because
    joining welds unrelated spans into commands that were never written:
    "The `infrahubctl` CLI ... name the transform `spine_config`" becomes
    the invocation `infrahubctl spine_config`. Callers scan each region.  # cli-check: ignore

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
            if sub not in GROUPS[group]:
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
