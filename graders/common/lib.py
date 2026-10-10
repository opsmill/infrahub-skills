"""Shared grader library for cross-cutting infrahub-common rules.

Currently covers the documentation-fallback behavior of
`workflow-information-priority.md`: when a task is not covered by any
loaded skill, the answer must consult the official docs and say so.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(["docs-fallback"], Path("output.md"))
    print(result)
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path


def load_output(path: Path) -> str:
    """Read the model's output file as text."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# Any of these phrases signals the answer flags the point as outside the
# skill's tested guidance (a gap) and/or leans on the official docs.
_CAVEAT_MARKERS = [
    "not covered",
    "not part of",
    "outside",
    "isn't covered",
    "is not covered",
    "verify",
    "official doc",
    "docs say",
    "gap",
    "not in the skill",
]


def check_docs_fallback(text: str) -> tuple[bool, str]:
    """A gap-fill answer must cite a docs.infrahub.app page and flag the gap.

    Fails if the answer silently resolves the gap from training with no
    documentation citation, or cites the docs without flagging that the
    point is outside the skill's tested rules.
    """
    lower = text.lower()
    cites = "docs.infrahub.app" in lower
    caveat = any(marker in lower for marker in _CAVEAT_MARKERS)
    if not cites:
        return False, "Answer does not cite a docs.infrahub.app page"
    if not caveat:
        return False, "Answer cites docs but lacks a gap/verify caveat"
    return True, "Cites docs.infrahub.app and flags the gap"


# ---------------------------------------------------------------------------
# infrahubctl command truth
#
# The tree and the code-region scanner live in cli_tree.py, imported here as
# a sibling: the eval harness puts this directory on sys.path, so the
# grader stays standalone while the tree stays written down once.
# scripts/check-cli-invocations.py loads the same module and asks the same
# question of the repository's own prose.
# ---------------------------------------------------------------------------

from cli_tree import FENCE, LEAVES, SPAN, code_regions, invalid_invocations  # noqa: E402


def check_cli_commands_exist(text: str) -> tuple[bool, str]:
    """Every `infrahubctl ...` command in the answer must be a real command.

    Guards the invented-subcommand class directly: a group given a
    subcommand it does not have, or a leaf given a generic verb where its
    positional target belongs. Both read plausibly and both fail on first
    use. graders/common/cli_tree.py holds the tree they are checked against.
    """
    if not text.strip():
        return False, "no output to check"
    if "infrahubctl" not in text:
        return False, "answer names no infrahubctl command at all"
    bad = invalid_invocations(text)
    if bad:
        return False, f"command(s) that do not exist: {sorted(set(bad))}"
    return True, "all infrahubctl commands referenced exist"


# Words that turn a following command mention into a contrast rather than a
# recommendation: "use transform, not render spine_config".
_NEGATED_BEFORE = re.compile(
    r"\b(not|never|instead of|rather than|avoid|don't|do not|isn't|is not|"
    r"wrong|incorrect|won't|will not|fails?)\b[^.\n]{0,40}$"
)


def check_python_transform_dry_run(
    text: str, transform_name: str = "spine_config"
) -> tuple[bool, str]:
    """A Python transform must be dry-run with `transform`, never `render`.

    `render` resolves names against `jinja2_transforms` only, so pointing it
    at a `python_transforms` entry prints "Unable to find <name>", which
    reads as an unregistered transform rather than the wrong command. The
    reader concludes the gate is unavailable and skips it.

    Both tests name the transform, so a bare mention of `infrahubctl
    transform` in a contrast sentence no longer clears the check while the
    answer aims `render` at the same transform.

    The transform name is a check parameter, not a constant: registered as
    `python-transform-dry-run:<name>`, so a second task with a different
    fixture does not have to reuse this one's.
    """
    lower = text.lower()
    # Accept either separator: a model may write spine-config for spine_config.
    named = "[_-]".join(
        re.escape(part) for part in re.split(r"[_-]", transform_name.lower())
    )
    if not re.search(rf"infrahubctl\s+transform\s+{named}", lower):
        return False, "does not aim `infrahubctl transform` at the named Python transform"
    # `render` may legitimately appear to draw the contrast, and the task's
    # own expectations ask for exactly that ("recommends transform, *not*
    # render"). What must not appear is render aimed at the named python
    # transform as a recommendation, so a negated mention is allowed.
    for match in re.finditer(rf"infrahubctl\s+render\s+{named}", lower):
        preceding = lower[max(0, match.start() - 60):match.start()]
        if not _NEGATED_BEFORE.search(preceding):
            return False, "recommends `infrahubctl render` for a python_transforms entry"
    return True, "uses `infrahubctl transform` for the named Python transform"


# The probe is the create/delete *pair*. `branch create` on its own is
# handed to the model by the task prompt ("I am about to run `infrahubctl
# branch create` ..."), so an answer that restates the user's plan would
# score on it. `branch delete` appears nowhere in the prompt.
_WRITE_PROBE_CREATE = re.compile(r"branch\s+create\b")
_WRITE_PROBE_DELETE = re.compile(r"branch\s+delete\b")

# The answer must also say, in words, that a green connectivity result is
# not clearance to write. Any one of these forms counts.
_NOT_PROOF_PATTERNS = [
    r"(does not|doesn't|do not|don't|never)[^.\n]{0,70}"
    r"(prove|proof|confirm|guarantee|establish|mean you have)"
    r"[^.\n]{0,70}(write|token|auth|permission)",
    r"(not|no)\s+proof[^.\n]{0,70}(write|token|auth|permission)",
    r"green[^.\n]{0,90}(not enough|insufficient|not sufficient|not clearance|proves nothing)",
    r"reads?\s+(are|is)\s+(served\s+)?anonymous",
    r"anonymous(ly)?[^.\n]{0,70}read",
]


_TOKEN_VAR = "INFRAHUB_API_TOKEN"

# `${TOKEN:-word}` / `${TOKEN-word}` with a non-empty fallback. The word
# substitutes only when the variable is *unset*, so this prints the token on
# exactly the runs where the token exists. Nobody writes this form except to
# print it, so it fails wherever it appears.
_TOKEN_FALLBACK = re.compile(rf"\$\{{{_TOKEN_VAR}:?-[^}}]+\}}")

# Forms that expand to the value: bare, braced, or an empty fallback. Safe
# as a test operand (`[ -n "${TOKEN:-}" ]`), unsafe as an argument to
# something that writes to stdout.
_TOKEN_VALUE = re.compile(rf"\$\{{?{_TOKEN_VAR}(?::?-)?\}}?(?![\w:?+])")

# `${TOKEN:+word}` and `${TOKEN:?word}` are the safe forms: the first can
# only ever expand to the word, the second writes to stderr and aborts.
_PRINTS_TO_STDOUT = re.compile(r"\b(?:echo|printf|print)\b")
# A backtick is a command boundary too. Without it an English sentence
# containing the word "echo" counted as one command, so a safe
# `${TOKEN:-}` test operand quoted later in the same sentence was reported
# as a leak — the very presence test the rule recommends.
_COMMAND_BREAK = re.compile(r";|\|\||&&|\||\n|`|\bthen\b|\bdo\b|\bfi\b|\bdone\b")


def _command_pieces(text: str) -> list[tuple[int, str]]:
    """Split into command-sized pieces, keeping each piece's offset."""
    pieces: list[tuple[int, str]] = []
    pos = 0
    for match in _COMMAND_BREAK.finditer(text):
        pieces.append((pos, text[pos : match.start()]))
        pos = match.end()
    pieces.append((pos, text[pos:]))
    return pieces


def _is_negated(text: str, start: int) -> bool:
    """Whether what starts at ``start`` is introduced as something to avoid.

    Case-folded here rather than in ``_NEGATED_BEFORE``: the other caller
    passes text that is already lowered.
    """
    return bool(_NEGATED_BEFORE.search(text[max(0, start - 60) : start].lower()))


def check_token_not_printed(text: str) -> tuple[bool, str]:
    """A presence test for the token must not be able to print its value.

    The distinction is the expansion, not the intent: `${TOKEN:-is NOT set}`
    reads as a presence test and substitutes the word only when the variable
    is unset, so on every run where the token exists it prints the token —
    into the terminal, the shell history and the retained CI log. Forms that
    cannot reach stdout with the value pass: an explicit `[ -n ... ]`
    conditional, `${TOKEN:+set}`, or `: "${TOKEN:?not set}"`.

    A leaking form quoted in order to warn against it is not a leak. The
    rule teaches this trap by name, so the best answer names it too — and
    matching it here failed the answer for repeating the lesson.
    """
    if not text.strip():
        return False, "no output to check"
    offenders = {
        m.group(0)
        for m in _TOKEN_FALLBACK.finditer(text)
        if not _is_negated(text, m.start())
    }
    for start, piece in _command_pieces(text):
        if not _PRINTS_TO_STDOUT.search(piece):
            continue
        if _is_negated(text, start):
            continue
        offenders.update(m.group(0) for m in _TOKEN_VALUE.finditer(piece))
    if offenders:
        return False, (
            f"expansion(s) that print the token's value: {sorted(offenders)}; "
            "use a presence test that can only print a fixed string"
        )
    return True, "no expansion that can print the token's value"


def check_preflight_write_probe(text: str) -> tuple[bool, str]:
    """A pre-flight before a write must not rest on `infrahubctl info` alone.

    With no token set, `info` skips the user lookup entirely and reports a
    green status, so it passes on exactly the misconfiguration it exists to
    catch. Two things must be present, and neither is available by echoing
    the prompt: the create *and* delete pair that probes a write, and an
    explicit statement that a green result is not write authorisation. An
    answer that says "your green `info` means you are good to go" fails on
    both.
    """
    lower = text.lower()
    if not (_WRITE_PROBE_CREATE.search(lower) and _WRITE_PROBE_DELETE.search(lower)):
        return False, "no write probe: expected a throwaway `branch create` and `branch delete` pair"
    if not any(re.search(p, lower) for p in _NOT_PROOF_PATTERNS):
        return False, "does not state that a green `infrahubctl info` is not proof of write access"
    # The claim has to be affirmative. "A green `info` does not confirm the
    # token is present" is the rule's own sentence, and matching it here
    # failed the best possible answer.
    claims_token_valid = re.search(
        r"info(?![^.\n]{0,80}\b(?:not|never|n't|nothing|no)\b)"
        r"[^.\n]{0,80}(token is valid|validates the token|confirms the token)",
        lower,
    )
    if claims_token_valid:
        return False, "claims `infrahubctl info` confirms the token is valid"
    return True, "probes a write and states that a green `info` is not write authorisation"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------

# One invocation is one line. `\s` crosses newlines, so the argument tail
# swallowed whatever the fence held next: a correct
# `infrahubctl generator create_dc site_id=abc --branch dry-run` followed by
# an inspection comment failed the bare-target check on the words of the
# comment. `[^\S\n]` is horizontal whitespace only.
_GENERATOR_INVOCATION = re.compile(
    r"infrahubctl[^\S\n]+generator[^\S\n]+([a-z0-9][\w.-]*)"
    r"((?:[^\S\n]+[^\s`]+)*)",
    re.IGNORECASE,
)

# A command continued with a trailing backslash is still one command.
_LINE_CONTINUATION = re.compile(r"\\\n[^\S\n]*")


def _positional_args(rest: str) -> list[str]:
    """Tokens after the generator name that are not flags or flag values.

    A flag is assumed to take a value, so `--branch dry-run` consumes both.
    That over-consumes after a boolean flag, which costs a missed check
    rather than a false failure — the safer direction for a gate.

    A `#` ends the command: everything after it is a comment, not an
    argument.
    """
    tokens = rest.split()
    out: list[str] = []
    skip = False
    for token in tokens:
        if token.startswith("#"):
            break
        if skip:
            skip = False
            continue
        if token.startswith("-"):
            skip = "=" not in token
            continue
        out.append(token)
    return out


def check_generator_target_is_key_value(text: str) -> tuple[bool, str]:
    """A generator target is a query variable, never a bare id.

    `infrahubctl generator` parses everything after the name as `key=value`
    and drops a token without an `=`. With no variables left it falls back
    to running the generator over every member of the target group, so a
    bare id is a mass write rather than the single-target run the author
    intended. The run also has to name a branch, because it writes.

    An invocation introduced as something *not* to write is a
    counter-example, not a recommendation. The rule teaches the bare-target
    failure by showing it, and the task prompt asks what goes wrong when the
    argument shape is wrong, so the best answer shows it too — matching it
    here failed the answer for teaching the rule.
    """
    if not text.strip():
        return False, "no output to check"
    folded = _LINE_CONTINUATION.sub(" ", text)
    recommended = 0
    for match in _GENERATOR_INVOCATION.finditer(folded):
        if _is_negated(folded, match.start()):
            continue
        recommended += 1
        name, rest = match.group(1), match.group(2)
        args = _positional_args(rest)
        if not args:
            return False, f"`generator {name}` passes no target at all"
        bare = [a for a in args if "=" not in a]
        if bare:
            return False, (
                f"`generator {name}` passes a bare token {bare!r}; a target is "
                "a `key=value` query variable, and a bare token is dropped"
            )
        if "--branch" not in rest:
            return False, f"`generator {name}` runs with no --branch, so it writes to main"
    if not recommended:
        return False, (
            "answer recommends no `infrahubctl generator <name> ...` invocation"
        )
    return True, "generator target is a key=value variable on a named branch"


# ---------------------------------------------------------------------------
# schema.graphql is generated output
# ---------------------------------------------------------------------------

_SCHEMA_FILE = r"(?:\./)?schema\.graphql"

# The command that writes the file. Spelled out in full rather than matched
# on the word `export`, so `infrahubctl schema export` — a different command
# writing a different artifact — cannot satisfy it.
_EXPORT_SCHEMA = re.compile(r"infrahubctl[^\S\n]+graphql[^\S\n]+export-schema\b")

# A command whose target is the file: an editor, an in-place rewrite, a
# patch, or a redirection onto it. Scanned inside code regions only, so the
# prose *around* the fix is never read as the fix. That boundary is the
# whole point: the task prompt hands the model a hand-edit to judge, so a
# good answer discusses one at length, and every attempt here to tell a
# discussion from an instruction by its wording failed a correct answer.
# `export-schema --destination schema.graphql` names the file too and is
# deliberately not matched — there the file is the command's output.
_SCHEMA_WRITE_CMD = re.compile(
    r"\b(?:vim?|nvim|nano|emacs|code|subl|open)\b[^\n`]{0,60}" + _SCHEMA_FILE
    + r"|\bsed\b[^\n`]{0,80}-i\b[^\n`]{0,80}" + _SCHEMA_FILE
    + r"|\bpatch\b[^\n`]{0,60}" + _SCHEMA_FILE
    + r"|>>?[^\S\n]*" + _SCHEMA_FILE
)

# An instruction to write the file by hand. Told apart from a description of
# one by mood, not by vocabulary: an authoring verb opening a sentence or a
# clause, with the file as its object.
#
#   caught:  "... still missing. Edit `schema.graphql` and add the field."
#   caught:  "Add the `serial_number` field to `schema.graphql` by hand."
#   passes:  "hand-editing `schema.graphql` is the wrong fix"
#   passes:  "After the export, `schema.graphql` will show the new field:"
#   passes:  "Add the field in YAML, not `schema.graphql`."
#   passes:  "Add the field to your schema YAML, then re-export `schema.graphql`."
#
# Only the base form counts, so the gerund in "hand-editing ... is the wrong
# fix" is not an instruction. The last two cases are handled after the match
# rather than inside it, by `_REGEN_CLAIMS_FILE` and the negation window
# below: a gap wide enough for a real instruction is also wide enough to
# reach past the verb's own object, and tightening it instead put an
# explicit "add the field to `schema.graphql` by hand" outside the window.
_HAND_EDIT_LEAD = (
    r"(?:^|[.!?;,\n]|\b(?:and|so|then|but)\b)[ \t]*(?:[*\-+]|\d+\.)?[ \t]*(?:\*\*)?"
    r"(?:(?:just|simply|then|now|manually|instead)[ \t]+)*"
)
# Prose wraps. "Edit\n`schema.graphql` and add the attribute" is one
# instruction split across two lines, so the gap has to survive a single
# newline — but not a blank one, which ends the paragraph and with it any
# claim that the filename is still this verb's object.
_SOFT_WRAP = r"(?:[^.\n]|\n(?!\s*\n))"

_HAND_EDIT_IMPERATIVE = re.compile(
    _HAND_EDIT_LEAD
    + r"(?P<verb>hand[- ]edit|edit|add|append|insert|paste|patch|write)\b"
    + r"(?P<gap>" + _SOFT_WRAP + r"{0,80}?)"
    + _SCHEMA_FILE,
    re.IGNORECASE,
)

# `open` is the one verb that needs a second look: "Open `schema.graphql`
# and confirm the field landed" is a verification step, so it counts only
# when an authoring verb follows. `type` is not one of those, however much
# "type this in" sounds like it — it is SDL vocabulary, and "confirm the
# `type DcimDevice` block lists serial_number" is a verification too.
_OPEN_THEN_AUTHOR = re.compile(
    _HAND_EDIT_LEAD
    + r"(?P<verb>open)\b(?P<gap>" + _SOFT_WRAP + r"{0,80}?)"
    + _SCHEMA_FILE
    + _SOFT_WRAP + r"{0,60}\b(?:add|append|insert|paste|write)\b",
    re.IGNORECASE,
)

# Between the verb and the filename, a word that hands the file to a
# different verb. "Add the field to your schema YAML, then re-export
# `schema.graphql`" instructs an edit of the YAML; the file belongs to the
# re-export, not to the `Add`.
#
# The `re-` prefix is optional because plenty of correct answers say "run
# the export to update `schema.graphql`" or "export it again so
# `schema.graphql` matches" — the same hand-off without the prefix. It was
# mandatory while the gap was 25 characters, which hid the problem: those
# gaps run to 50-60 characters and never reached the filename at all.
_REGEN_CLAIMS_FILE = re.compile(
    r"(?:re-?)?export|re-?generat|refresh|re-?run", re.IGNORECASE
)


def check_graphql_schema_regenerated(text: str) -> tuple[bool, str]:
    """`schema.graphql` is export output, refreshed by command, never typed.

    `infrahubctl graphql export-schema` fetches the schema from the server
    and rewrites the whole file, so a field typed into it by hand is gone at
    the next export and, until then, the local file disagrees with the
    server every query is validated against. The check asks which mechanism
    the answer puts the missing field there with: the export command, or an
    editor.

    Evidence is ranked, and only two things count: a command aimed at the
    file, then an instruction to write it by hand, then the absence of the
    export command. The task prompt hands the model a hand-edit to judge,
    so a good answer discusses one at length, which is why the second
    signal reads mood rather than vocabulary.

    A third signal used to flag a GraphQL fence holding schema content, on
    the theory that handing over the SDL is the same edit without naming
    the file. It failed an answer that ran the export and then showed the
    regenerated result so the reader could confirm the field landed — a
    natural and fully compliant shape. Excusing a fence that any export
    precedes, the obvious repair, leaves the signal catching only answers
    that show SDL and never export at all, which the export check below
    already fails. It was removed rather than patched.

    Known gap, accepted: an answer that runs the export and then says
    "paste this in" without naming the file passes. Catching it needs the
    fence signal back, and that one is removed for cause.

    That gap is not evidence of a safe error direction. An earlier version
    of this docstring claimed the only remaining direction was a missed
    violation; review then found four phrasings wrong, two in each
    direction, so the claim is gone rather than restated. Every one of the
    four is a fixture below, which is where a claim like it belongs.
    """
    if not text.strip():
        return False, "no output to check"

    offenders: list[str] = []
    for region in code_regions(text):
        for match in _SCHEMA_WRITE_CMD.finditer(region):
            offenders.append(" ".join(match.group(0).split()))

    for pattern in (_HAND_EDIT_IMPERATIVE, _OPEN_THEN_AUTHOR):
        for match in pattern.finditer(text):
            if _REGEN_CLAIMS_FILE.search(match.group("gap")):
                continue
            # Negation is read from the verb's own clause and nowhere else:
            # from the verb to the filename, which is the span a negation
            # has to sit in to be about this instruction.
            #
            # There was a second, wider `_is_negated` lookback here. It read
            # across whatever boundary the lead anchored on, so a negation
            # in the previous clause suppressed a real hand-edit — "... is
            # not there yet; edit `schema.graphql` and add the attribute"
            # scored as correct. Widening the lead to `; , and so then but`
            # without widening `_NEGATED_BEFORE`'s `[^.\n]{0,40}$` left the
            # two disagreeing about where a clause ends. The window below
            # already covers in-clause negation, so the lookback only ever
            # reached text that was not this instruction's.
            # Newlines are collapsed first: `_NEGATED_BEFORE` stops at one,
            # so a wrapped clause would hide its own negation.
            clause = " ".join(text[match.start("verb") : match.end("gap")].split())
            if _NEGATED_BEFORE.search(clause.lower()):
                continue
            offenders.append(" ".join(match.group(0).split()))

    if offenders:
        return False, (
            f"treats schema.graphql as a source file: {sorted(set(offenders))}; "
            "it is `export-schema` output, and a hand-edit is overwritten"
        )

    for match in _EXPORT_SCHEMA.finditer(text):
        if not _is_negated(text, match.start()):
            return True, "refreshes schema.graphql with `infrahubctl graphql export-schema`"
    return False, (
        "answer never runs `infrahubctl graphql export-schema`, so nothing "
        "refreshes schema.graphql from the server"
    )


# ---------------------------------------------------------------------------
# The committed protocol file is regenerated from the server
# ---------------------------------------------------------------------------

# The command this check reads, taken from the pinned CLI tree so a rename
# there fails loudly here instead of leaving the check reading nothing.
_PROTOCOLS = "protocols"
assert _PROTOCOLS in LEAVES, "cli_tree.LEAVES no longer has `protocols`"

# `infrahubctl protocols` writes here when no `--out` is given.
_PROTOCOLS_DEFAULT_OUT = "schema_protocols.py"

# Options of `infrahubctl protocols` that take a value (infrahub-sdk 1.23.2).
# `--sync` / `--no-sync` take none. infrahubctl has no root options, so the
# subcommand is always the word right after the binary.
_PROTOCOLS_VALUE_OPTIONS = {"--schemas", "--branch", "--out", "--config-file"}

# Tokens that end one shell command and start the next. shlex with
# `punctuation_chars` emits these as tokens of their own, so a quoted `;`
# stays inside its argument instead of fabricating a second command.
_SHELL_OPERATORS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&"}

# A redirection takes the next word as its target, never as an argument.
_REDIRECTIONS = {"<", ">", ">>", "<<", "<<<", ">&", "<&", ">|", "&>", "&>>"}

# Programs that run another program, and, for each, the options that take a
# value. Any other option is read as a flag. A wrong guess leaves the binary
# somewhere other than argv[0], and the command is then unreadable, which
# fails the check rather than passing it.
_WRAPPERS: dict[tuple[str, ...], set[str]] = {
    ("sudo",): {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T",
                "--user", "--group", "--chdir", "--host", "--prompt"},
    ("env",): {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    ("uv", "run"): {"--with", "--with-editable", "--with-requirements", "--python",
                    "-p", "--project", "--directory", "--group", "--no-group",
                    "--extra", "--env-file", "--package", "--index",
                    "--default-index", "--from"},
    ("uvx",): {"--with", "--with-editable", "--with-requirements", "--python",
               "-p", "--from", "--index", "--default-index"},
    ("poetry", "run"): {"-C", "--directory", "-P", "--project"},
    ("pipx", "run"): {"--spec", "--python", "--pip-args", "--index-url"},
}

_ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")

# Words that print their arguments: `infrahubctl` after one of these is data.
_PRINT_WORDS = {"echo", "printf", "print"}

# `<path>`, `<branch>`: a placeholder, not a value. Swapped for one opaque
# word before lexing, because `<` and `>` would otherwise read as
# redirections and swallow the words around them.
_PLACEHOLDER = re.compile(r"<[A-Za-z][\w.-]*>")
_PLACEHOLDER_WORD = "__placeholder__"

# Characters that end an unquoted shell word.
_WORD_END = set(" \t;&|<>()")


def _code_regions_with_offsets(text: str) -> list[tuple[int, str, bool]]:
    """Fenced blocks and inline spans, each with its offset into ``text``.

    The same regions `code_regions` returns, but with offsets, so a span
    can be read against the prose just before it. The flag says whether
    the region is an inline span: only a span sits inside a sentence that
    can introduce it as something to avoid.
    """
    regions: list[tuple[int, str, bool]] = []
    blanked = list(text)
    for match in FENCE.finditer(text):
        regions.append((match.start(1), match.group(1), False))
        for i in range(match.start(), match.end()):
            if blanked[i] != "\n":
                blanked[i] = " "
    for match in SPAN.finditer("".join(blanked)):
        regions.append((match.start(1), match.group(1), True))
    return regions


def _read_word(line: str, i: int) -> tuple[str, int]:
    """The shell word starting at ``line[i]``, with its quotes removed."""
    word: list[str] = []
    while i < len(line) and line[i] not in _WORD_END:
        char = line[i]
        if char in "'\"":
            end = line.find(char, i + 1)
            if end == -1:
                return "", len(line)
            word.append(line[i + 1 : end])
            i = end + 1
        elif char == "\\":
            word.append(line[i + 1 : i + 2])
            i += 2
        else:
            word.append(char)
            i += 1
    return "".join(word), i


def _heredoc_delimiters(line: str) -> list[str]:
    """The delimiter of every heredoc the line opens, in order.

    Each delimiter is the full shell word after `<<` or `<<-`, quoted or
    not, so `EOF-marker` stays `EOF-marker`. A `<<<` here-string opens no
    heredoc, and `<<` inside quotes or a comment is not an operator. A
    `<<` with no word after it yields an empty string, which no line can
    terminate.
    """
    delimiters: list[str] = []
    quote = None
    i = 0
    while i < len(line):
        char = line[i]
        if quote:
            if char == quote:
                quote = None
            elif char == "\\" and quote == '"':
                i += 1
            i += 1
        elif char in "'\"":
            quote = char
            i += 1
        elif char == "\\":
            i += 2
        elif char == "#" and (i == 0 or line[i - 1] in _WORD_END):
            break
        elif line.startswith("<<<", i):
            i += 3
        elif line.startswith("<<", i):
            i += 2
            if line[i : i + 1] == "-":
                i += 1
            while line[i : i + 1] in (" ", "\t"):
                i += 1
            word, i = _read_word(line, i)
            delimiters.append(word)
        else:
            i += 1
    return delimiters


def _shell_lines(region: str) -> tuple[list[str], list[str]]:
    """The region's lines as the shell reads them, and the heredocs that never end.

    A `\\` continuation joins with no separator, as the shell does, and a
    heredoc body is data, so it is dropped. A heredoc whose terminator never
    comes takes the rest of the region with it; it is returned by its
    opening line, with the body it swallowed, so the caller can fail closed
    instead of reading the hidden lines as data.
    """
    joined = region.replace("\\\n", "")
    lines: list[str] = []
    unterminated: list[str] = []
    pending: list[str] = []
    opener = ""
    body: list[str] = []
    for line in joined.splitlines():
        if pending:
            if pending[0] and line.strip() == pending[0]:
                pending.pop(0)
                body = []
            else:
                body.append(line)
            continue
        lines.append(line)
        pending = _heredoc_delimiters(line)
        opener = line.strip()
        body = []
    if pending:
        unterminated.append("\n".join([opener, *body]))
    return lines, unterminated


def _split_commands(tokens: list[str]) -> list[list[str]]:
    """Cut a token list into commands, dropping redirections and their targets."""
    commands: list[list[str]] = [[]]
    skip = False
    for token in tokens:
        if skip:
            skip = False
            continue
        if token in _SHELL_OPERATORS:
            commands.append([])
        elif token in _REDIRECTIONS:
            skip = True
        else:
            commands[-1].append(token)
    return [c for c in commands if c]


def _peel_wrappers(argv: list[str]) -> int:
    """Index of the program that actually runs, after wrappers and `VAR=value`."""
    i = 0
    while i < len(argv):
        if _ENV_ASSIGNMENT.match(argv[i]):
            i += 1
            continue
        for wrapper, value_options in _WRAPPERS.items():
            names = [Path(w).name for w in argv[i : i + len(wrapper)]]
            if tuple(names) == wrapper:
                i += len(wrapper)
                while i < len(argv) and argv[i].startswith("-"):
                    if argv[i] == "--":
                        i += 1
                        break
                    flag, eq, _ = argv[i].partition("=")
                    i += 2 if flag in value_options and not eq else 1
                break
        else:
            return i
    return i


def _protocols_invocations(region: str) -> tuple[list[dict], list[str]]:
    """Every `infrahubctl protocols` command in one code region, parsed.

    Returns the readable commands, each with whether it reads local files
    (`--schemas`) and the file it writes (`--out`, or the CLI default), and
    the lines naming the command that could not be read.

    The program is argv[0] after wrappers (`sudo`, `env`, `VAR=value`,
    `uv run`, `uvx`, `poetry run`, `pipx run`). `infrahubctl` anywhere
    else is data when a print word runs it (`echo infrahubctl ...`), and
    unreadable otherwise (`time infrahubctl ...`, an unknown wrapper). An
    unreadable line fails the check: a parser gap must not read as a
    compliant answer.
    """
    found: list[dict] = []
    unreadable: list[str] = []
    lines, unterminated = _shell_lines(region)
    # A heredoc that never ends swallows the lines after it. If those lines
    # name the command, the parser cannot tell data from a hidden command.
    for swallowed in unterminated:
        if "infrahubctl" in swallowed and _PROTOCOLS in swallowed:
            unreadable.append(f"{swallowed.splitlines()[0]} (heredoc never ends)")
    for line in lines:
        lexer = shlex.shlex(
            _PLACEHOLDER.sub(_PLACEHOLDER_WORD, line), posix=True, punctuation_chars=True
        )
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            if "infrahubctl" in line and _PROTOCOLS in line:
                unreadable.append(line.strip())
            continue
        for argv in _split_commands(tokens):
            names = [Path(t).name for t in argv]
            if "infrahubctl" not in names:
                continue
            start = _peel_wrappers(argv)
            if start >= len(argv) or names[start] != "infrahubctl":
                if start < len(argv) and names[start] in _PRINT_WORDS:
                    continue
                at = names.index("infrahubctl")
                if names[at + 1 : at + 2] == [_PROTOCOLS]:
                    unreadable.append(" ".join(argv))
                continue
            if names[start + 1 : start + 2] != [_PROTOCOLS]:
                continue
            schemas = False
            out = _PROTOCOLS_DEFAULT_OUT
            args = argv[start + 2 :]
            j = 0
            while j < len(args):
                flag, eq, value = args[j].partition("=")
                if flag in _PROTOCOLS_VALUE_OPTIONS and not eq:
                    value = args[j + 1] if j + 1 < len(args) else ""
                    j += 1
                if flag == "--schemas":
                    schemas = True
                elif flag == "--out":
                    out = value
                j += 1
            found.append({"schemas": schemas, "out": out, "line": " ".join(argv[start:])})
    return found, unreadable


def _same_path(a: str, b: str) -> bool:
    """Whether two relative paths name the same file (`./lib/x` is `lib/x`)."""
    return Path(a.strip()).as_posix().removeprefix("./") == Path(b.strip()).as_posix().removeprefix("./")


def check_protocols_regenerated_from_server(
    text: str, committed: str = "lib/protocols.py"
) -> tuple[bool, str]:
    """The committed protocol file is regenerated from a running server.

    `infrahubctl protocols --schemas <dir>` builds the module from the local
    YAML alone. It emits no Profile or Template classes and none of the
    relationships that another schema file adds through `extensions`.
    Writing that output over a committed, server-generated file deletes
    classes and fields the repository's code imports.
    `skills/infrahub-common/rules/protocols-generated.md` therefore keeps
    `--schemas` for a scratch path only.

    The check parses the `infrahubctl protocols` commands in fenced blocks
    and inline code. It passes when a recommended command writes the
    committed file without `--schemas`, and no recommended command writes
    it with `--schemas`. It fails when no command writes that file, when
    any command that does reads local files, or when a line naming the
    command cannot be read. `--schemas` named in prose, as the offline
    option with its limits, is not a command and does not count either way.

    An inline span introduced as something to avoid ("do not run `...`")
    is a contrast, not a recommendation, so it is skipped. A fenced block
    is always a recommendation: it is the text a reader copies and runs.

    The eval task `common-protocols-regenerate-from-server` runs this check
    through `check_protocols_regenerated.py`, and that task is what guards
    the skill's prose. The fixtures in `tests/graders/test_common_lib.py`
    guard the check's own contract.

    The committed path is a check parameter
    (`protocols-regenerated-from-server:<path>`), so a task with a
    different layout does not have to reuse this one's.
    """
    if not text.strip():
        return False, "no output to check"

    writes_committed: list[dict] = []
    unreadable: list[str] = []
    for start, region, is_span in _code_regions_with_offsets(text):
        if is_span and _is_negated(text, start - 1):
            continue
        found, bad = _protocols_invocations(region)
        unreadable.extend(bad)
        writes_committed.extend(inv for inv in found if _same_path(inv["out"], committed))

    if unreadable:
        return False, (
            f"cannot read these `infrahubctl {_PROTOCOLS}` lines: {sorted(set(unreadable))}; "
            "give the command with infrahubctl as the program"
        )
    if not writes_committed:
        return False, (
            f"no `infrahubctl {_PROTOCOLS}` command writes {committed}, so the "
            "committed protocol file is never regenerated"
        )
    offline = sorted({inv["line"] for inv in writes_committed if inv["schemas"]})
    if offline:
        return False, (
            f"command(s) that write {committed} with --schemas: {offline}; offline "
            "output has no Profile or Template classes and no `extensions` "
            "relationships, so it must not overwrite the committed, "
            "server-generated file"
        )
    return True, f"regenerates {committed} from the server, without --schemas"


# A name may carry colon-separated arguments, e.g.
# `python-transform-dry-run:spine_config`, so a check that depends on a task
# fixture is not pinned to one task by its registry entry.
CHECKS = {
    "docs-fallback": check_docs_fallback,
    "cli-commands-exist": check_cli_commands_exist,
    "python-transform-dry-run": check_python_transform_dry_run,
    "preflight-write-probe": check_preflight_write_probe,
    "token-not-printed": check_token_not_printed,
    "generator-target-is-key-value": check_generator_target_is_key_value,
    "graphql-schema-regenerated": check_graphql_schema_regenerated,
    "protocols-regenerated-from-server": check_protocols_regenerated_from_server,
}


def _dispatch(name: str, text: str) -> tuple[bool, str]:
    base, _, args = name.partition(":")
    fn = CHECKS[base]
    return fn(text, *args.split(":")) if args else fn(text)


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against the output file and return skillgrade JSON."""
    text = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        try:
            ok, msg = _dispatch(name, text)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    if failed:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}


if __name__ == "__main__":  # pragma: no cover
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(list(CHECKS.keys()), out), indent=2))
