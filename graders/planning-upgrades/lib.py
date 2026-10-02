"""Shared grader library for infrahub-planning-upgrades skill evaluations.

The model is prompted to write a version-by-version upgrade plan to
``UPGRADE_PLAN.md`` in the cwd. The document has one ``##`` section per
version hop, in ascending order, each carrying a findings table with these
nine columns:

    | Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |

Every check here parses that structure — hop headings, table rows split into
named cells, fenced command blocks tokenised with ``shlex`` — and none of
them substring-matches the prose. See ``dev/guidelines/graders.md``.

Each check returns ``(bool, str)``: pass/fail plus a one-line message that
lands in the skillgrade report.

The plan describes *how* to move through each hop; it never hands the user an
upgrade command. The only commands it may show are the read-only probes in
``READ_ONLY_INVOCATIONS``, and a plan that shows none at all is fine.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shlex
from pathlib import Path

PLAN_FILE = "UPGRADE_PLAN.md"

REQUIRED_COLUMNS = [
    "change",
    "release",
    "kind",
    "severity",
    "when",
    "affected",
    "evidence",
    "action",
    "source",
]

VALID_KIND = {"breaking", "preparation"}
VALID_SEVERITY = {"critical", "warning", "info"}
VALID_WHEN = {"before", "during", "after"}
VALID_AFFECTED = {"yes", "no", "unknown"}

# Read-only probes the plan may show, as token prefixes. An allowlist rather
# than a blocklist on purpose: `infrahubctl schema load` puts its verb in the
# *third* token, so anything keyed on the first subcommand lets a write past.
READ_ONLY_INVOCATIONS = [
    ("infrahubctl", "info"),
    ("infrahubctl", "version"),
    ("infrahubctl", "schema", "check"),
    ("infrahubctl", "branch", "list"),
    ("infrahub", "db", "showmigrations"),
    ("infrahub", "db", "migrate"),  # only with a flag below
    ("infrahub", "upgrade"),  # only with a flag below
]

# Commands that write unless one of these flags makes them report instead. Both
# return before applying anything: `upgrade --check`, and `db migrate --check`
# (every 1.x) or `--plan` (from 1.10.0), checked in backend/infrahub/cli/.
READ_ONLY_FLAGS: dict[tuple[str, ...], set[str]] = {
    ("infrahub", "upgrade"): {"--check"},
    ("infrahub", "db", "migrate"): {"--check", "--plan"},
}
_PERMITTED = ", ".join(
    " ".join(inv) + (" " + "|".join(sorted(READ_ONLY_FLAGS[inv])) if inv in READ_ONLY_FLAGS else "")
    for inv in READ_ONLY_INVOCATIONS
)

# A CLI subcommand token. Prose that happens to open with the binary name
# ("`infrahub GitHub releases, read 2026-09-26`" in a Source cell) is not an
# invocation; a live trial failed on exactly that span.
_SUBCOMMAND_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_BINARIES = ("infrahub", "infrahubctl")

# The infrahubctl tree is the one the CLI gate pins, loaded by path so this
# grader and scripts/check-cli-invocations.py cannot disagree about it.
_TREE_SPEC = importlib.util.spec_from_file_location(
    "planning_upgrades_cli_tree", Path(__file__).resolve().parent.parent / "common" / "cli_tree.py"
)
_cli_tree = importlib.util.module_from_spec(_TREE_SPEC)
_TREE_SPEC.loader.exec_module(_cli_tree)

# The server binary's top-level commands across 1.x (backend/infrahub/cli/__init__.py);
# `git-agent` is gone from 1.11.0 but still named by plans for older hops.
_SERVER_COMMANDS = {"server", "db", "events", "tasks", "dev", "upgrade", "recover", "shell", "git-agent"}
_KNOWN_SUBCOMMANDS = {
    "infrahub": _SERVER_COMMANDS,
    # `upgrade` does not exist on infrahubctl; it is kept here so the invented
    # command is recognised as an invocation and reported, not skipped.
    "infrahubctl": set(_cli_tree.GROUPS) | set(_cli_tree.LEAVES) | {"upgrade"},
}

# `infrahubctl` has no `upgrade` command at all — it lives server-side in
# backend/infrahub/cli/upgrade.py. Writing it is an invented command, which is
# the exact failure mode safety-read-only-probes exists to catch. It is listed
# separately so the message says "invented", not "not allowed".
NONEXISTENT_INVOCATIONS = [("infrahubctl", "upgrade")]

# Commands that write. A fenced block is what a plan offers to run, so it is
# held to the allowlist above. An inline code span may only *name* a command
# ("1.11.0 removed `infrahub git-agent`"), which a live trial was failed for,
# so a span fails only when it names one of these, an invented command, or
# `infrahub upgrade` without --check.
# Derived from the pinned CLI tree rather than kept by hand: a hand list missed
# `object delete`, `object update`, and `object create`.
_WRITE_VERBS = {"create", "delete", "load", "merge", "rebase", "update", "add"}
_WRITE_LEAVES = {"load", "generator", "run"}
WRITE_INVOCATIONS = (
    [("infrahub", "db", "migrate")]
    + sorted(
        ("infrahubctl", group, sub)
        for group, subs in _cli_tree.GROUPS.items()
        for sub in subs & _WRITE_VERBS
    )
    + sorted(("infrahubctl", leaf) for leaf in _cli_tree.LEAVES & _WRITE_LEAVES)
)

# Writes that run with no argument. Any other write named bare in prose is a
# name, not a handover: the 1.11.0 notes say `pyarrow` stays available "for
# `infrahubctl object load`", and a live trial quoting that was failed. A write
# someone could run carries its target (`infrahubctl object load objects/`).
BARE_RUNNABLE_WRITES = [("infrahub", "db", "migrate")]

# A leading `v` is allowed: upstream tags read `infrahub-v1.10.0`, so plans
# write `v1.10` too, and `\b` alone never matched between `v` and the digit.
_VERSION_RE = re.compile(r"(?<![\d.])v?(\d+)\.(\d+)(?:\.(\d+))?(?!\d)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_FENCE_OPEN_RE = re.compile(r"^\s*(```+|~~~+)")
_LIST_MARKER_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

# Evidence that names something locatable, strongest first.
#
# Widened after a live trial: a plan backed a verdict with
# "GraphQL `{ Branch { name } }` returns only `main`", which is exactly the
# concrete evidence the rule asks for and which the first draft rejected,
# because `Branch` carries no namespace prefix and the cell held no path.
# A check that fails that answer is grading vocabulary. See
# dev/guidelines/graders.md § "Verify both directions", false-fail half.
_EV_PATH = re.compile(r"[\w./-]+\.(?:ya?ml|py|gql|graphql|j2|toml|json|cfg)\b")
_EV_DOTTED_KIND = re.compile(r"\b[A-Z][A-Za-z0-9]+\.[a-z_][A-Za-z0-9_]*\b")
# No bare-CamelCase pattern: `GitHub`, `GraphQL` and `PostgreSQL` read as
# schema kinds, so "See the GitHub release notes" passed as evidence. A kind
# meant as an artifact is backticked (_EV_CODE_SPAN) or dotted (_EV_DOTTED_KIND).
_EV_COUNT = re.compile(
    r"\b\d+\s+(?:(?:node|object|instance|device|match|result|row|occurrence|hit|branch"
    r"|definition|file|artifact|generator)s?|repositor(?:y|ies))\b",
    re.I,
)
# `grep`/`rg` count: a search over the repo's schema files settles a repo-side
# unknown as surely as a live read settles an instance-side one. A live trial
# was failed for proposing exactly that.
# The Infrahub probes are the read-only allowlist itself, so one list decides
# both what a plan may run and what counts as naming a probe. The bare binary
# name does not count: "check with your infrahub admin" names no probe.
_EV_PROBE = re.compile(
    r"\b(?:get_schema|query_graphql|get_nodes|search_nodes|showmigrations|(?i:grep)|rg)\b"
    + "".join(
        "|\\b" + r"\s+".join(re.escape(w) for w in inv)
        + (
            r"\s+(?:" + "|".join(re.escape(f) for f in sorted(READ_ONLY_FLAGS[inv])) + ")"
            if inv in READ_ONLY_FLAGS
            else ""
        )
        + "\\b"
        for inv in READ_ONLY_INVOCATIONS
    )
)
# A GraphQL query in backticks is a probe the user can run as written; a live
# trial resolved an unknown with `query { CoreWebhook { ... } }`.
_EV_GRAPHQL = re.compile(r"`\s*(?:query\b[^`{]*)?\{[^`]*\}\s*`")
# A backticked shell command in an Action is a probe the user can run as
# written: `pip show infrahub-sdk` settles an SDK-version unknown, and a live
# trial was failed for it. A span with no argument (`infrahub-sdk`) is a name,
# not a command.
# Restricted to read-only inspection commands: any backticked phrase with a
# space (`review the repo`) used to pass as a probe.
_EV_COMMAND = re.compile(
    r"`\s*(?:pip\s+(?:show|freeze|list)|uv\s+pip\s+(?:show|list)|grep|rg|git\s+(?:diff|log|show|grep|status)"
    r"|cat|ls|find|head|tail|jq|yq|docker(?:\s+compose)?\s+(?:ps|images|config|inspect)"
    r"|kubectl\s+(?:get|describe)|helm\s+(?:get|list|history|status)|upgrade\s+--check)"
    r"(?:\s[^`]*)?`"
)
# A backticked span is a named artifact: a query, a command, a field, a value.
_EV_CODE_SPAN = re.compile(r"`[^`]+`")

_NO_EVIDENCE_SENTINELS = {"", "-", "--", "n/a", "na", "none", "tbd", "?"}


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------


def _cell(value: str) -> str:
    """An enum cell's value with markdown emphasis and code ticks stripped.

    A live trial wrote `**yes**`; the verdict is the same, only the markup
    differs, so it must grade the same.
    """
    return value.strip().strip("*_`").strip().lower()


def _versions(text: str) -> list[tuple[int, int]]:
    """Every version in the text as (major, minor); patch is deliberately dropped."""
    return [(int(m.group(1)), int(m.group(2))) for m in _VERSION_RE.finditer(text)]


def _full_versions(text: str) -> list[str]:
    """Every version in the text, without a leading ``v``."""
    return [
        ".".join(g for g in m.groups() if g is not None) for m in _VERSION_RE.finditer(text)
    ]


def hop_sections(text: str) -> list[dict]:
    """Split the plan into ``##`` sections that name two or more versions.

    A hop heading is any level-2 heading carrying at least two versions, so
    ``## 1.6 -> 1.7`` and ``## Step 1 - 1.6.3 to 1.7.7`` both parse. Headings
    with fewer than two versions (``## Summary``) are not hops.
    """
    sections: list[dict] = []
    current: dict | None = None
    fence: str | None = None
    for line in text.splitlines():
        # Both fence styles, closed only by the same character: a `~~~` example
        # holding "## 1.3 -> 1.4" was read as a hop.
        opener = _FENCE_OPEN_RE.match(line)
        if opener and (fence is None or (opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence))):
            fence = None if fence is not None else opener.group(1)
            if current is not None:
                current["lines"].append(line)
            continue
        if fence is not None:
            # A `# comment` inside a fenced block is not a heading.
            if current is not None:
                current["lines"].append(line)
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            vs = _versions(heading)
            if len(vs) >= 2:
                current = {"heading": heading, "from": vs[0], "to": vs[-1], "lines": []}
                sections.append(current)
            else:
                current = None
            continue
        if line.startswith("# "):
            current = None
            continue
        if current is not None:
            current["lines"].append(line)
    for s in sections:
        s["body"] = "\n".join(s["lines"])
    return sections


def _minor_hops(sections: list[dict]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """The minor-version hops a plan's sections describe, in order.

    Same-minor sections are patch roll-ups (1.9.1 -> 1.9.6) and are left out;
    N-1 says nothing about them. A section whose range holds two or more other
    minor hops is an overview ("## Overview: 1.5.2 -> 1.10.0" above five hops),
    and identical ranges collapse to one, so a title such as
    "## Upgrade plan: 1.9.2 to 1.10.0" above "## 1.9 -> 1.10" is one hop.
    """
    overviews = _overview_ranges(sections)
    ranges = [(sec["from"], sec["to"]) for sec in sections if sec["from"] != sec["to"]]
    return [r for r in dict.fromkeys(ranges) if r not in overviews]


def _overview_ranges(sections: list[dict]) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    """Ranges that hold two or more other distinct minor hops: overviews, not hops.

    Same-minor (patch) sections do not count towards the two, so patch roll-ups
    either side of a hop never turn the hop itself into an overview.
    """
    distinct = list(dict.fromkeys((s["from"], s["to"]) for s in sections if s["from"] != s["to"]))

    def _inside(outer: tuple, inner: tuple) -> bool:
        return outer != inner and outer[0] <= inner[0] and inner[1] <= outer[1]

    return {r for r in distinct if sum(1 for o in distinct if _inside(r, o)) >= 2}


def tables(body: str) -> list[list[dict]]:
    """Parse every markdown table in ``body`` into a list of row dicts."""
    out: list[list[dict]] = []
    rows = [ln.strip() for ln in body.splitlines()]
    block: list[str] = []
    for line in rows + [""]:
        if line.startswith("|"):
            block.append(line)
            continue
        if len(block) >= 2:
            parsed = _parse_table(block)
            if parsed:
                out.append(parsed)
        block = []
    return out


# A cell boundary is an unescaped pipe. Markdown tables escape a literal pipe
# as `\|`; a live trial wrote `git diff ... \| grep ...` in an Action cell and
# a naive split cut the command in half.
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def _cells(row: str) -> list[str]:
    inner = row.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [c.strip().replace("\\|", "|") for c in _CELL_SPLIT_RE.split(inner)]


def _parse_table(block: list[str]) -> list[dict]:
    header = [_cell(c) for c in _cells(block[0])]
    body_rows = block[1:]
    # Drop the --- separator row if present.
    if body_rows and set(body_rows[0].replace("|", "").replace(":", "").strip()) <= {
        "-",
        " ",
    }:
        body_rows = body_rows[1:]
    parsed: list[dict] = []
    for row in body_rows:
        cells = _cells(row)
        if not any(cells):
            continue
        parsed.append(
            {header[i]: cells[i] for i in range(min(len(header), len(cells)))}
        )
    return parsed


def findings(text: str) -> list[dict]:
    """Every findings row across every hop, each tagged with its hop heading."""
    out: list[dict] = []
    sections = hop_sections(text)
    # A roll-up table under "## Overview: 1.6.0 -> 1.9.0" summarises the hops
    # below it; grading it as a hop's findings failed correct plans.
    overviews = _overview_ranges(sections)
    for sec in sections:
        if (sec["from"], sec["to"]) in overviews:
            continue
        for table in tables(sec["body"]):
            for row in table:
                if "change" in row and "affected" in row:
                    row = dict(row)
                    row["_hop"] = sec["heading"]
                    out.append(row)
    return out


_QUOTING_COLUMNS = ("change", "evidence")


def _blank_quoting_cells(text: str) -> str:
    """Empty the Change and Evidence cells of every findings table.

    Those cells quote what exists: the command a release removed, or the line
    in the user's repo that still calls it. A live trial backticked
    `infrahub git-agent start` from the user's tasks.py as evidence and was
    failed for "handing over" a command it was reporting. The Action cell, the
    prose and every fence are still read, so a command offered as a step
    cannot hide here.
    """
    out: list[str] = []
    blank: list[int] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            blank = []
            out.append(line)
            continue
        cells = _CELL_SPLIT_RE.split(stripped.strip("|"))
        names = [_cell(c) for c in cells]
        if "change" in names and "evidence" in names:
            blank = [names.index(c) for c in _QUOTING_COLUMNS]
            out.append(line)
            continue
        for i in blank:
            if i < len(cells):
                cells[i] = " "
        out.append("|" + "|".join(cells) + "|")
    return "\n".join(out)


# Fence languages a plan offers to run. A ```yaml or ```python fence quotes a
# file (the user's compose file, a transform), and a live-looking line in it is
# not a handover; a review found `command: infrahub git-agent start` failed.
_RUNNABLE_FENCES = {"", "sh", "bash", "zsh", "shell", "console", "shell-session"}
_BINARY_WORD_RE = re.compile(r"(?<![\w-])infrahub(?:ctl)?(?![\w-])")
_OPERATORS = {"&&", "||", ";", "|", "&", ";;", "|&"}


def _split_code(text: str) -> tuple[list[str], str, list[str]]:
    """Runnable code lines, the prose with every code block removed, and quoted lines.

    Code is a backtick or tilde fence at any indent (a fence inside a list item
    is indented), or an indented block: four or more spaces after a blank line,
    not a list item. The indented form was invisible to a column-0 fence regex,
    so a plan could hand over `infrahub upgrade` in one and pass. Only
    unlabelled and shell fences, and indented blocks, count as runnable. Inline
    spans are then read from the prose only, since a fence's backticks shifted
    the pairing and made later prose read as code. Lines in other fences
    (```text, ```yaml) come back as quoted: an output block or a quoted file.
    """
    code: list[str] = []
    quoted: list[str] = []
    prose: list[str] = []
    fence: str | None = None
    runnable = False
    in_indented = False
    prev_blank = True
    # Content indent of the list item the text is in, if any. Inside a list an
    # indented block needs four spaces beyond it, so continuation prose such as
    # "    infrahub stays on 1.10" under "1. Take the hop." is not code.
    list_indent = 0
    for line in text.splitlines():
        marker = _LIST_ITEM_RE.match(line)
        if marker:
            list_indent = len(marker.group(0))
        elif line.strip() and not line.startswith((" ", "\t")):
            list_indent = 0
        opener = _FENCE_OPEN_RE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
            elif runnable:
                code.append(line)
            else:
                quoted.append(line)
            prose.append("")
            prev_blank = False
            continue
        if opener:
            fence = opener.group(1)
            info = line.strip()[len(fence):].strip().split()
            runnable = (info[0].lower() if info else "") in _RUNNABLE_FENCES
            in_indented = False
            prose.append("")
            prev_blank = False
            continue
        need = list_indent + 4
        indented = line.strip() != "" and (
            line.startswith("\t") or len(line) - len(line.lstrip(" ")) >= need
        )
        if indented and (in_indented or prev_blank) and not _LIST_MARKER_RE.match(line.strip()):
            in_indented = True
            code.append(line)
            prose.append("")
            prev_blank = False
            continue
        if line.strip():
            in_indented = False
        prev_blank = line.strip() == ""
        prose.append(line)
    return _join_continuations(code), "\n".join(prose), _join_continuations(quoted)


def _join_continuations(lines: list[str]) -> list[str]:
    """Join backslash-continued lines, so a flag on the next line stays with its command."""
    out: list[str] = []
    buf = ""
    for raw in lines:
        stripped = raw.strip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        out.append(buf + stripped)
        buf = ""
    if buf:
        out.append(buf)
    return out


def command_lines(text: str) -> list[tuple[str, bool]]:
    """Every runnable code line, plus inline code spans from the prose.

    Each line comes back with ``True`` when it sat in a code block. Drops
    comment lines so a ``#`` annotation cannot be read as a command.
    """
    lines: list[tuple[str, bool]] = []
    code, prose, _quoted = _split_code(text)
    for raw in code:
        stripped = raw.strip().lstrip("$").strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((stripped, True))
    for span in _INLINE_CODE_RE.findall(_blank_quoting_cells(prose)):
        stripped = span.strip().lstrip("$").strip()
        if stripped and not stripped.startswith("#"):
            lines.append((stripped, False))
    return lines


_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHELLS = {"sh", "bash", "zsh", "ash", "dash"}
_PREFIX_WRAPPERS = {"sudo", "doas", "env", "time", "nohup", "exec", "command"}
_RUN_WRAPPERS = {"uv", "poetry", "pipenv", "pdm", "hatch", "rye"}
# Programs that are not Infrahub: `docker compose exec infrahub bash` runs bash
# in a service named `infrahub`.
_PROGRAMS = _SHELLS | {"python", "python3", "cat", "ls", "echo", "env", "printenv", "true"}
# Options that consume the next token, per wrapper.
_VALUE_OPTS = {
    "sudo": {
        "-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "--user", "--group",
        "--host", "--prompt", "--chdir", "--close-from", "--role", "--type",
        "--other-user", "--login-class",
    },
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "uv": {
        "--group", "--only-group", "--extra", "--with", "--with-editable",
        "--with-requirements", "-p", "--python", "--project", "--directory",
        "--package", "--env-file", "--index", "--index-url", "--default-index",
        "--extra-index-url", "-f", "--find-links",
    },
    "poetry": {"-C", "--directory", "-P", "--project"},
    "pdm": {"-p", "--project"},
    "docker": {
        "-e", "--env", "--env-file", "-u", "--user", "-w", "--workdir", "--name",
        "--entrypoint", "-v", "--volume", "-p", "--publish", "-l", "--label",
        "--network", "-f", "--file", "--project-name", "--project-directory",
        "--profile", "-c", "--context", "--index", "--platform",
    },
    "ssh": {
        "-p", "-i", "-l", "-o", "-F", "-J", "-b", "-c", "-D", "-E", "-e", "-I",
        "-L", "-m", "-O", "-Q", "-R", "-S", "-W", "-w",
    },
}


def _split_ops(line: str) -> list[list[str]]:
    """The line's simple commands, tokenised once with shell operators kept apart.

    Tokenising the whole line, rather than splitting on `&&`/`;`/`|` first, is
    what dev/guidelines/graders.md asks for: a pre-split cuts inside quotes.
    Raises ValueError when the line cannot be tokenised.
    """
    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    segments: list[list[str]] = [[]]
    for tok in lex:
        if tok in _OPERATORS:
            segments.append([])
        else:
            segments[-1].append(tok)
    return [seg for seg in segments if seg]


def _skip_opts(tokens: list[str], j: int, wrapper: str) -> int:
    """Index of the first non-option token from j, stepping over option values."""
    values = _VALUE_OPTS.get(wrapper, set())
    while j < len(tokens) and tokens[j].startswith("-"):
        if tokens[j] == "--":  # option terminator: what follows is not an option
            return j + 1
        j += 2 if tokens[j] in values else 1
    return j


def _commands(tokens: list[str]) -> list[list[str]]:
    """The commands a simple command runs, each as an argv, wrappers peeled off.

    Only a token in command position is a program: the segment's start, or past
    a wrapper's options (`sudo -E`, `env FOO=1`, `uv run`), past the service of
    `docker [compose] exec|run`, past `--` for `kubectl`, or inside the command
    string of `sh -c '...'` and `ssh host '...'`, which are tokenised again. A
    binary name anywhere else is an argument (`echo "back up infrahub"`, a
    service or namespace named `infrahub`) and is not a call.
    Raises ValueError when a command string cannot be tokenised.
    """
    i = 0
    while i < len(tokens) and _ASSIGN_RE.match(tokens[i]):
        i += 1
    if i >= len(tokens):
        return []
    head = tokens[i].rsplit("/", 1)[-1]
    if head in _PREFIX_WRAPPERS:
        j = i + 1
        while j < len(tokens) and (
            tokens[j].startswith("-") or (head == "env" and _ASSIGN_RE.match(tokens[j]))
        ):
            if tokens[j] == "--":  # option terminator: the command follows
                j += 1
                break
            j += 2 if tokens[j] in _VALUE_OPTS.get(head, set()) else 1
        return _commands(tokens[j:])
    if head in _RUN_WRAPPERS and i + 1 < len(tokens) and tokens[i + 1] == "run":
        return _commands(tokens[_skip_opts(tokens, i + 2, head):])
    if head in _SHELLS:
        for j in range(i + 1, len(tokens) - 1):
            flag = tokens[j]
            if flag.startswith("-") and not flag.startswith("--") and "c" in flag[1:]:
                return _command_string(tokens[j + 1])
        return []
    if head == "ssh":
        j = _skip_opts(tokens, i + 1, "ssh") + 1  # past the host
        return _command_string(" ".join(tokens[j:])) if j < len(tokens) else []
    if head == "docker":
        j = i + 1
        if j < len(tokens) and tokens[j] == "compose":
            j = _skip_opts(tokens, j + 1, "docker")
        if j >= len(tokens) or tokens[j] not in ("exec", "run"):
            return []
        j = _skip_opts(tokens, j + 1, "docker")
        if j >= len(tokens):
            return []
        service, rest = tokens[j], tokens[j + 1 :]
        # A `--` or stray options after the service belong to the command line,
        # not to the program: `exec infrahub -- infrahubctl version`.
        rest = rest[_skip_opts(rest, 0, "docker"):]
        # A service token that is itself a binary name, followed by something
        # that is not a program, reads as the binary: `docker compose run --rm
        # infrahub migrate` means `infrahub migrate`, while `exec infrahub bash`
        # runs bash.
        if service.rsplit("/", 1)[-1] in _BINARIES and rest and not rest[0].startswith("-") and rest[0].rsplit("/", 1)[-1] not in (
            _PROGRAMS | set(_BINARIES)
        ):
            return [[service, *rest]]
        return _commands(rest)
    if head == "kubectl":
        return _commands(tokens[tokens.index("--") + 1 :]) if "--" in tokens else []
    return [tokens[i:]]


def _command_string(text: str) -> list[list[str]]:
    out: list[list[str]] = []
    for seg in _split_ops(text):
        out.extend(_commands(seg))
    return out


def invocations(text: str) -> list[tuple[str, tuple[str, ...], list[str], bool, str]]:
    """Every ``infrahub`` / ``infrahubctl`` invocation, as (binary, path, flags, fenced, line).

    ``path`` is the binary followed by its non-flag tokens, so
    ``infrahubctl schema load x.yml`` yields
    ``("infrahubctl", "schema", "load", "x.yml")``. Keying on the first
    subcommand alone would read that as ``schema`` and miss the write.

    Only a binary in command position counts; see `_commands` for the
    wrappers it sees through. In a code block, a subcommand-shaped word the
    binary does not have is kept as an invented command so the check can fail
    it. A line that names a binary but cannot be tokenised comes back as an
    ``<unparseable>`` invocation, so the check fails closed rather than
    reporting "no commands".
    """
    return _invocations_from(command_lines(text), fail_closed=True)


def quoted_invocations(text: str) -> list[tuple[str, tuple[str, ...], list[str], bool, str]]:
    """Invocations inside non-shell fences (```text, ```yaml), never fail-closed.

    An output block or a quoted file is not a handover, so only the upgrade
    itself and the invented upgrade subcommand on infrahubctl are graded here; an output
    line with an odd quote (`don't`) is skipped rather than failed.
    """
    _code, _prose, quoted = _split_code(text)
    lines = [(ln.strip(), True) for ln in quoted if ln.strip() and not ln.strip().startswith("#")]
    return _invocations_from(lines, fail_closed=False)


def _invocations_from(
    lines: list[tuple[str, bool]], fail_closed: bool
) -> list[tuple[str, tuple[str, ...], list[str], bool, str]]:
    found: list[tuple[str, tuple[str, ...], list[str], bool, str]] = []
    for line, fenced in lines:
        try:
            argvs = [argv for seg in _split_ops(line) for argv in _commands(seg)]
        except ValueError:
            if fail_closed and _BINARY_WORD_RE.search(line):
                found.append(("?", ("<unparseable>",), [], fenced, line))
            continue
        for argv in argvs:
            base = argv[0].rsplit("/", 1)[-1]
            if base not in _BINARIES:
                continue
            rest = argv[1:]
            words = [t for t in rest if not t.startswith("-")]
            flags = [t for t in rest if t.startswith("-")]
            if not words:
                continue
            # In a code block, a subcommand-shaped word the binary does not
            # have is an invented command (`infrahub migrate`). In prose the
            # binary name may just be a word in a sentence, so it is skipped.
            known = words[0] in _KNOWN_SUBCOMMANDS[base]
            if known or (fenced and _SUBCOMMAND_RE.match(words[0])):
                found.append((base, tuple([base, *words]), flags, fenced, line))
    return found


def _is_concrete_evidence(cell: str) -> bool:
    """Does the cell name something a reader could go and look at?

    Ranked, strongest first: a file path, a ``Kind.attribute`` reference, a
    schema kind, a counted result, or a named probe. Prose that merely
    restates the finding matches none of these.
    """
    value = cell.strip().strip("`").strip()
    if value.lower() in _NO_EVIDENCE_SENTINELS:
        return False
    for pattern in (
        _EV_PATH,
        _EV_DOTTED_KIND,
        _EV_COUNT,
        _EV_PROBE,
        _EV_CODE_SPAN,
    ):
        if pattern.search(cell):
            return True
    return False


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def check_sequential_hops(
    text: str, source: str = "", target: str = ""
) -> tuple[bool, str]:
    """Hop headings enumerate every minor from source to target, ascending, no skips."""
    hops = hop_sections(text)
    if not hops:
        return (
            False,
            f"no hop sections found in {PLAN_FILE} (expected '## X.Y -> X.Z' headings)",
        )

    src = _versions(source)[0] if _versions(source) else hops[0]["from"]
    tgt = _versions(target)[0] if _versions(target) else hops[-1]["to"]

    def _fmt(pairs: list[tuple[tuple[int, int], tuple[int, int]]]) -> str:
        return ", ".join(f"{a[0]}.{a[1]}->{b[0]}.{b[1]}" for a, b in pairs)

    if tgt < src:
        return False, f"target {tgt[0]}.{tgt[1]} is older than source {src[0]}.{src[1]}"
    if src == tgt:
        # Source and target share a minor (1.9.1 -> 1.9.6). Patches within a
        # minor can be skipped: one upgrade applies every pending migration in
        # order, and N-1 constrains minors only. The plan is one section that
        # stays inside that minor.
        crossing = [h for h in hops if h["from"] != h["to"]]
        if crossing:
            return False, (
                f"source and target are both {src[0]}.{src[1]}, but the plan crosses a "
                f"minor: '{crossing[0]['heading']}'"
            )
        return True, f"patch upgrade within {src[0]}.{src[1]}: {len(hops)} section(s), no minor crossed"

    # Within one major the hops are known exactly. Across a major (1.11 ->
    # 2.0) the last minor of the old major is not in the plan's inputs, so
    # the chain is checked link by link instead: each hop is the next minor,
    # or the first minor of the next major.
    expected: list[tuple[tuple[int, int], tuple[int, int]]] | None = None
    if src[0] == tgt[0]:
        expected = [((src[0], m), (src[0], m + 1)) for m in range(src[1], tgt[1])]

    def _one_step(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return b == (a[0], a[1] + 1) or (b[0] == a[0] + 1 and b[1] == 0)

    # A hop whose endpoints share a minor is a patch roll-up (1.10.8 -> 1.10.10),
    # which is good practice before a minor move and which the N-1 rule says
    # nothing about. Drop those before comparing; this check grades the *minor*
    # progression. A live trial produced exactly this shape and the first draft
    # rejected it.
    actual = _minor_hops(hops)
    want = _fmt(expected) if expected else f"one minor at a time from {src[0]}.{src[1]} to {tgt[0]}.{tgt[1]}"
    if not actual:
        return False, (
            f"plan has {len(hops)} section(s) but none crosses a minor version; expected {want}"
        )
    chained = (
        actual[0][0] == src
        and actual[-1][1] == tgt
        and all(actual[i][1] == actual[i + 1][0] for i in range(len(actual) - 1))
        and all(_one_step(a, b) for a, b in actual)
    )
    if chained:
        return True, f"{len(actual)} sequential minor hops, no skips"
    if len(actual) == 1:
        return False, (
            f"plan has a single hop {_fmt(actual)} but the N-1 rule requires "
            f"sequential hops: {want}"
        )
    return False, f"hops are [{_fmt(actual)}], expected [{want}]"


def check_every_hop_enumerated(text: str, releases: str = "") -> tuple[bool, str]:
    """Findings name each intermediate release that carries a breaking change.

    Also rejects a ``Release`` cell holding a range rather than one version:
    ``1.6.0-1.9.0`` names no actual change and is the shape a plan reaches for
    when it wants credit for intermediate releases it never read.
    """
    rows = findings(text)
    if not rows:
        return False, f"no findings rows parsed from {PLAN_FILE}"

    ranged = [r for r in rows if len(_full_versions(r.get("release", ""))) > 1]
    if ranged:
        return False, (
            f"{len(ranged)} findings carry a version range in Release "
            f"(e.g. '{ranged[0].get('release')}') instead of a single release"
        )

    required = [v.strip() for v in releases.split(",") if v.strip()]
    if not required:
        return True, f"{len(rows)} findings, all stamped with a single release"

    seen = {r.get("release", "").strip() for r in rows}
    seen_mm = {tuple(_versions(s)[0]) for s in seen if _versions(s)}
    missing = []
    for req in required:
        req_mm = _versions(req)[0]
        if req not in seen and req_mm not in seen_mm:
            missing.append(req)
    if missing:
        return False, (
            f"no finding attributed to release(s) {', '.join(missing)}; "
            f"releases present: {', '.join(sorted(s for s in seen if s)) or '(none)'}"
        )
    return True, f"findings cover all {len(required)} required releases"


def check_verdict_has_evidence(text: str) -> tuple[bool, str]:
    """Every finding carries a verdict, and the verdict is backed by something locatable."""
    rows = findings(text)
    if not rows:
        return False, f"no findings rows parsed from {PLAN_FILE}"

    for row in rows:
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in row]
        if missing_cols:
            return False, (
                f"finding '{row.get('change', '?')}' is missing column(s): "
                f"{', '.join(missing_cols)}"
            )

    for row in rows:
        change = row.get("change", "?")
        affected = _cell(row.get("affected", ""))
        if affected not in VALID_AFFECTED:
            return False, (
                f"finding '{change}' has Affected='{row.get('affected')}', "
                f"expected one of {sorted(VALID_AFFECTED)}"
            )
        if affected in ("yes", "no"):
            if not _is_concrete_evidence(row.get("evidence", "")):
                return False, (
                    f"finding '{change}' is Affected={affected} but Evidence "
                    f"'{row.get('evidence')}' names no locatable artifact "
                    f"(path, Kind.attribute, schema kind, count, or probe)"
                )
        else:
            # A named file to read settles an unknown as surely as a named tool:
            # a live trial said to read the image tags in docker-compose.yml.
            action = row.get("action", "")
            if not (
                _EV_PROBE.search(action)
                or _EV_PATH.search(action)
                or _EV_GRAPHQL.search(action)
                or _EV_COMMAND.search(action)
            ):
                return False, (
                    f"finding '{change}' is Affected=unknown but Action "
                    f"'{row.get('action')}' names no probe that would resolve it"
                )
    return True, f"all {len(rows)} findings carry a backed verdict"


def check_finding_vocabulary(text: str) -> tuple[bool, str]:
    """Kind, Severity and When use the documented enums."""
    rows = findings(text)
    if not rows:
        return False, f"no findings rows parsed from {PLAN_FILE}"
    for row in rows:
        for col, valid in (
            ("kind", VALID_KIND),
            ("severity", VALID_SEVERITY),
            ("when", VALID_WHEN),
        ):
            value = _cell(row.get(col, ""))
            if value not in valid:
                return False, (
                    f"finding '{row.get('change', '?')}' has {col.title()}='{row.get(col)}', "
                    f"expected one of {sorted(valid)}"
                )
    return True, f"all {len(rows)} findings use the documented enums"


def check_no_mutating_commands(text: str) -> tuple[bool, str]:
    """The plan shows only read-only probes, and no invented commands."""
    # A non-shell fence is output or a quoted file, so only the upgrade itself
    # and the invented command fail there; a review found the upgrade handed
    # over in a ```text block passed once only shell fences were read.
    for _binary, path, flags, _fenced, line in quoted_invocations(text):
        where = f" (non-shell fence: {line[:120]!r})"
        if path[: len(NONEXISTENT_INVOCATIONS[0])] == NONEXISTENT_INVOCATIONS[0]:
            return False, f"'{' '.join(path)}'{where} is not a real command"
        if path[:2] == ("infrahub", "upgrade") and not set(flags) & READ_ONLY_FLAGS[("infrahub", "upgrade")]:
            return False, (
                f"'{' '.join(path)}'{where} without --check is an upgrade command handed to the user"
            )
    invoked = invocations(text)
    if not invoked:
        return True, f"{PLAN_FILE} shows no commands; nothing to execute"

    for _binary, path, flags, fenced, line in invoked:
        # Quote the line and where it sat: the plan is gone after a trial, so
        # the message is all a reader gets.
        shown = " ".join(path)
        where = f" ({'code block' if fenced else 'inline'}: {line[:120]!r})"
        if path == ("<unparseable>",):
            return False, (
                f"a command naming infrahub could not be parsed{where}; "
                f"failing closed rather than treating it as absent"
            )
        if len(path) > 1 and path[1] not in _KNOWN_SUBCOMMANDS.get(path[0], set()):
            return False, f"'{shown}'{where} is not a real command"
        for bad in NONEXISTENT_INVOCATIONS:
            if path[: len(bad)] == bad:
                return False, (
                    f"'{shown}'{where} is not a real command — upgrade lives server-side in "
                    f"backend/infrahub/cli/upgrade.py, not in infrahubctl"
                )
        guarded = next((g for g in READ_ONLY_FLAGS if path[: len(g)] == g), None)
        if guarded is not None:
            if set(flags) & READ_ONLY_FLAGS[guarded]:
                continue
            if guarded == ("infrahub", "upgrade"):
                return False, (
                    f"'{shown}'{where} without --check is an upgrade command handed to the user; "
                    f"the plan describes each hop, it does not give the upgrade command"
                )
            return False, f"'{shown}'{where} writes to Infrahub; the plan runs read-only probes only"
        if not fenced:
            write = next((w for w in WRITE_INVOCATIONS if path[: len(w)] == w), None)
            if (
                write is not None
                and len(path) == len(write)
                and not flags
                and write not in BARE_RUNNABLE_WRITES
            ):
                continue
            if write is not None:
                return False, f"'{shown}'{where} writes to Infrahub; the plan runs read-only probes only"
            continue
        allowed = next((a for a in READ_ONLY_INVOCATIONS if path[: len(a)] == a), None)
        if allowed is None:
            return False, (
                f"'{shown}'{where} is not on the read-only probe allowlist "
                f"(permitted: {_PERMITTED})"
            )
    return True, f"all {len(invoked)} invocations are read-only probes"


CHECKS = {
    "sequential-hops": check_sequential_hops,
    "every-hop-enumerated": check_every_hop_enumerated,
    "verdict-has-evidence": check_verdict_has_evidence,
    "finding-vocabulary": check_finding_vocabulary,
    "no-mutating-commands": check_no_mutating_commands,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the plan text; return skillgrade JSON."""
    text = output_path.read_text(errors="ignore") if output_path.exists() else ""
    entries: list[dict] = []
    passed_count = 0

    for spec in check_specs:
        name, kwargs = spec if isinstance(spec, tuple) else (spec, {})
        fn = CHECKS.get(name)
        if fn is None:
            entries.append(
                {"name": name, "passed": False, "message": f"Unknown check: {name}"}
            )
            continue
        try:
            ok, msg = fn(text, **kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        display = (
            name
            if not kwargs
            else f"{name}({','.join(f'{k}={v}' for k, v in kwargs.items())})"
        )
        entries.append({"name": display, "passed": ok, "message": msg})

    total = len(check_specs)
    score = round(passed_count / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}


def main_cli() -> None:
    import sys

    if len(sys.argv) < 3:
        print("usage: python lib.py <output-file> <check-name> ...", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(run_checks(list(sys.argv[2:]), Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main_cli()
