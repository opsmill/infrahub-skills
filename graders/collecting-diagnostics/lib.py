"""Shared grader library for the infrahub-collecting-diagnostics skill.

The rewritten skill recommends a sequence of ``infrahub-collect`` commands
rather than producing a bundle directory. Evals therefore grade the model's
plan text: each check inspects the recommended-commands output for the right
invocation, flags, and cautions. Check functions take ``(text, **kwargs)`` and
return ``(passed, message)``. Return shape matches sibling grader libs so
skillgrade ingests it identically.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Callable

CheckResult = tuple[bool, str]
CheckFn = Callable[..., CheckResult]


def check_mentions_create(text: str, **_: object) -> CheckResult:
    """Plan recommends `infrahub-collect create`."""
    if re.search(r"infrahub-collect\s+create", text):
        return True, "recommends `infrahub-collect create`"
    return False, "missing `infrahub-collect create` invocation"


def check_mentions_env_detect(text: str, **_: object) -> CheckResult:
    """Plan recommends `infrahub-collect environment detect`."""
    if re.search(r"infrahub-collect\s+environment\s+detect", text):
        return True, "recommends `environment detect`"
    return False, "missing `infrahub-collect environment detect`"


def check_mentions_flag(text: str, *, flag: str = "", **_: object) -> CheckResult:
    """A specific create flag appears in the plan."""
    if not flag:
        return False, "check_mentions_flag requires flag kwarg"
    # Match the flag as a whole CLI token: allow backtick/bracket/quote/space
    # boundaries (Markdown-rendered flags), but reject longer flags that merely
    # start with it (e.g. --benchmark-only when flag is --benchmark).
    if re.search(rf"(?<!\w){re.escape(flag)}(?![\w-])", text):
        return True, f"plan includes `{flag}`"
    return False, f"expected flag `{flag}` not found"


def check_review_before_sharing(text: str, **_: object) -> CheckResult:
    """Plan surfaces a review-before-sharing caution."""
    low = text.lower()
    has_review = "review" in low and ("shar" in low or "send" in low or "bundle" in low)
    has_mask_gap = "key name" in low or "key-name" in low or "mask" in low or "redact" in low
    if has_review or has_mask_gap:
        return True, "surfaces review-before-sharing caution"
    return False, "no review-before-sharing caution found"


def check_cross_link_reporting_issues(text: str, **_: object) -> CheckResult:
    """Plan cross-links the reporting-issues skill for public issues."""
    if re.search(r"reporting-issues", text, re.IGNORECASE):
        return True, "cross-links infrahub-reporting-issues"
    return False, "missing infrahub-reporting-issues cross-link"


def check_no_legacy_artifacts(text: str, **_: object) -> CheckResult:
    """Plan does NOT resurrect the old hand-rolled artifacts."""
    legacy = ("manifest.yml", "flags.yml", "redaction-report.txt", "infrahubctl telemetry")
    hits = [name for name in legacy if name in text]
    if hits:
        return False, f"plan references retired artifacts: {hits}"
    return True, "no legacy hand-rolled artifacts referenced"


# --- Traces of slow requests (rules/create-traces.md) --- #
#
# The plan is Markdown: prose plus fenced shell blocks. The trace checks read
# the commands from the fences with shlex, and the offer, the request for a
# token and the HTTP calls from the prose split into sentences. The fences are
# removed from the prose first, so a command is never read as a sentence.

# A fence opens with three or more backticks or tildes and closes with the same
# run, so a plan that wraps its block in four backticks is still read.
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
# A shell prompt in front of a command, as in a `console` block: `$ curl ...`.
_PROMPT_RE = re.compile(r"^([ \t]*)\$[ \t]+", re.MULTILINE)
_TRACE_OPTION_RE = re.compile(r"^--(include-traces|traces-[a-z-]+)(=|$)")
_NEGATION_RE = re.compile(r"\b(never|not|no|don't|do not|without)\b", re.IGNORECASE)
# The full path, so a call to another endpoint with the same last segment does not count.
_RATIO_PATH = "/api/troubleshooting/trace-sample-ratio"


# Clause boundaries inside a sentence. A negation counts only in the clause
# that holds the verb, and only before that verb: "Paste the token here; I
# will not log it." is still a request, but "Do not send me the token." is not.
# The same holds for the HTTP method of a call in prose.
# A colon is a boundary only before whitespace, so the colon of `https://` or
# of `host:8000` does not cut a URL in two. "and" is a boundary, except after
# a negation and one verb: "Do not copy and paste the token here." keeps its
# negation on both verbs, while "Don't worry about it and send me the token"
# is still a request.
_CLAUSE_SPLIT_RE = re.compile(r"[;,]|:(?=\s)|\s+[—–-]\s+|\s+(?:but|so|then)\s+", re.IGNORECASE)
_AND_SPLIT_RE = re.compile(r"\s+and\s+", re.IGNORECASE)
_NEGATED_VERB_RE = re.compile(r"^\s*(never|not|don't|don’t|do not)\s+\w+\s*$", re.IGNORECASE)


def _clauses(sentence: str) -> list[str]:
    """The clauses of a sentence, for reading a negation before a verb."""
    clauses: list[str] = []
    for part in _CLAUSE_SPLIT_RE.split(sentence):
        pieces = _AND_SPLIT_RE.split(part)
        merged = [pieces[0]]
        for piece in pieces[1:]:
            if _NEGATED_VERB_RE.match(merged[-1]):
                merged[-1] = f"{merged[-1]} and {piece}"
            else:
                merged.append(piece)
        clauses.extend(merged)
    return clauses
_NEGATION_BEFORE_RE = re.compile(r"\b(never|not|no|don't|don’t|do not|without)\b", re.IGNORECASE)


def _fenced_blocks(text: str) -> list[str]:
    """The content of every fenced code block, in order."""
    return [m.group(2) for m in _FENCE_RE.finditer(text)]


def _prose(text: str) -> str:
    """The plan with its fenced code blocks removed."""
    return _FENCE_RE.sub("\n", text)


def _sentences(prose: str) -> list[str]:
    """Prose split into sentences and list items, with Markdown markers removed."""
    # Join the wrapped lines of a paragraph or list item first, so a question
    # that wraps over two lines is still one sentence.
    items: list[str] = []
    current: list[str] = []
    for line in prose.splitlines():
        starts_item = re.match(r"^\s*(?:[-*+>]|\d+[.)]|#+)\s+", line)
        if not line.strip() or starts_item:
            if current:
                items.append(" ".join(current))
            current = []
        text = re.sub(r"^\s*(?:[-*+>]|\d+[.)]|#+)\s+", "", line).strip()
        if text:
            current.append(text)
    if current:
        items.append(" ".join(current))
    parts: list[str] = []
    for item in items:
        parts.extend(s.strip() for s in re.split(r"(?<=[.?!])\s+", item) if s.strip())
    return parts


def _shell_lines(text: str) -> list[tuple[str, list[list[str]]]]:
    """Every shell line in the fences, in order: the raw line and its commands.

    Each command is a list of shlex tokens without comments. A line that
    shlex cannot split keeps its raw text with no commands.
    """
    lines: list[tuple[str, list[list[str]]]] = []
    for block in _fenced_blocks(text):
        joined = re.sub(r"\\\n", " ", _PROMPT_RE.sub(r"\1", block))
        for line in joined.splitlines():
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                lines.append((line, []))
                continue
            # A line may chain commands; shlex keeps `&&`, `;` and `|` as tokens
            # when they stand apart, so split on those tokens only.
            commands: list[list[str]] = []
            current: list[str] = []
            for tok in tokens:
                if tok in ("&&", "||", ";", "|"):
                    if current:
                        commands.append(current)
                    current = []
                else:
                    current.append(tok)
            if current:
                commands.append(current)
            lines.append((line, commands))
    return lines


def _shell_commands(text: str) -> list[list[str]]:
    """Every shell command in the fences, as shlex tokens without comments."""
    return [cmd for _, commands in _shell_lines(text) for cmd in commands]


def _create_options(text: str) -> list[list[str]]:
    """The options of every `infrahub-collect create` command in the fences."""
    found: list[list[str]] = []
    for cmd in _shell_commands(text):
        for i in range(len(cmd) - 1):
            if cmd[i].endswith("infrahub-collect") and cmd[i + 1] == "create":
                found.append(cmd[i + 2:])
                break
    return found


def _option_value(options: list[str], name: str) -> str:
    """The value of an option, as `--name value` or `--name=value`; empty when absent."""
    for i, opt in enumerate(options):
        if opt.startswith(f"{name}="):
            return opt.split("=", 1)[1]
        if opt == name and i + 1 < len(options) and not options[i + 1].startswith("-"):
            return options[i + 1]
    return ""


def _trace_options(options: list[str]) -> set[str]:
    names = set()
    for opt in options:
        m = _TRACE_OPTION_RE.match(opt)
        if m:
            names.add(f"--{m.group(1)}")
    return names


# Traces in the sense of the collected traces, not an error's stack trace:
# "Did you get a stack trace in the task-worker logs?" is a normal question for
# a schema load failure and offers nothing.
_TRACES_WORD_RE = re.compile(r"(?<!stack )(?<!stack-)\btrac(e|es|ing)\b", re.IGNORECASE)


def _asks_about_traces(text: str) -> bool:
    """A question in the prose that names the collected traces."""
    return any(
        s.endswith("?") and _TRACES_WORD_RE.search(s)
        for s in _sentences(_prose(text))
    )


def check_traces_offered_with_window(text: str, *, window: str = "any", **_: object) -> CheckResult:
    """For a slow instance: ask about traces, and give the command with a window.

    `window` is the window the scenario calls for: "absolute" for a slowness
    that has ended (`--traces-start` and `--traces-end`), "any" when either
    form fits. The command also passes `--traces-min-duration`, which the rule
    asks for even when the operator keeps the default `1s`. The option counts
    only as a token of the command, not in a shell comment or in prose.
    """
    def has_window(names: set[str]) -> bool:
        absolute = {"--traces-start", "--traces-end"} <= names
        if window == "absolute":
            return absolute and "--traces-since" not in names
        return absolute or "--traces-since" in names

    with_window = [
        opts for opts in _create_options(text)
        if "--include-traces" in _trace_options(opts) and has_window(_trace_options(opts))
    ]
    if not with_window:
        wanted = (
            "`--traces-start` and `--traces-end` (the slowness has ended)"
            if window == "absolute"
            else "`--traces-since` or `--traces-start` and `--traces-end`"
        )
        return False, f"no `infrahub-collect create --include-traces` command with {wanted}"
    if not all(_option_value(opts, "--traces-min-duration") for opts in with_window):
        return False, "a traces command with a window does not pass `--traces-min-duration <duration>`"
    if not _asks_about_traces(text):
        return False, "adds traces without asking the operator first (no question names traces)"
    return True, "asks about traces and gives the command with a window"


def check_traces_not_offered(text: str, **_: object) -> CheckResult:
    """For a problem that is not slowness: no trace option and no offer."""
    used = set().union(*(_trace_options(o) for o in _create_options(text))) if _create_options(text) else set()
    if used:
        return False, f"adds trace options for a problem that is not slowness: {sorted(used)}"
    if _asks_about_traces(text):
        return False, "offers traces for a problem that is not slowness"
    recommends = [
        s for s in _sentences(_prose(text))
        if re.search(r"--include-traces\b", s) and not _NEGATION_RE.search(s)
    ]
    if recommends:
        return False, f"recommends `--include-traces` for a problem that is not slowness: {recommends[0]!r}"
    return True, "does not offer traces"


# The caveat of rules/create-traces.md, step 3: only a share of requests has a
# trace. A sentence that names traces and says "only a share", "not every", or
# names the sampling, with no negation before "sampl" ("Every request has a
# trace, with no sampling." says the opposite).
_TRACED_RE = re.compile(r"(?<!stack )(?<!stack-)\btrac(e|es|ed|ing)\b", re.IGNORECASE)
_SHARE_RE = re.compile(
    r"\b(only|just)\s+(a\s+)?(share|part|fraction|subset|portion|sample|some)\b|\bnot\s+(every|all)\b",
    re.IGNORECASE,
)
_SAMPLING_RE = re.compile(r"\bsampl(ed|ing)\b", re.IGNORECASE)


def _states_sampling_caveat(sentence: str) -> bool:
    if not _TRACED_RE.search(sentence):
        return False
    if _SHARE_RE.search(sentence):
        return True
    m = _SAMPLING_RE.search(sentence)
    return bool(m) and not _NEGATION_BEFORE_RE.search(sentence[: m.start()])


def check_sampling_caveat(text: str, **_: object) -> CheckResult:
    """Say that only a share of requests has a trace, set by the sampling ratio."""
    if any(_states_sampling_caveat(s) for s in _sentences(_prose(text))):
        return True, "says that only a share of requests has a trace"
    return False, "does not say that only a share of requests has a trace (sampling)"


_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _without_env_prefix(cmd: list[str]) -> list[str]:
    """The command from its command word on, without `VAR=value` prefixes."""
    i = 0
    while i < len(cmd) and _ASSIGN_RE.match(cmd[i]):
        i += 1
    return cmd[i:]


def _ratio_methods(text: str) -> set[str]:
    """HTTP methods the plan gives for the sampling ratio endpoint."""
    methods: set[str] = set()
    for cmd in _shell_commands(text):
        cmd = _without_env_prefix(cmd)
        if not any(_RATIO_PATH in tok for tok in cmd) or not cmd or not cmd[0].endswith("curl"):
            continue
        method = "GET"
        for i, tok in enumerate(cmd):
            if tok in ("-X", "--request") and i + 1 < len(cmd):
                method = cmd[i + 1].upper()
            elif tok.startswith("-X") and len(tok) > 2:
                method = tok[2:].upper()
            elif tok.startswith("--request="):
                method = tok.split("=", 1)[1].upper()
        methods.add(method)
    for s in _sentences(_prose(text)):
        for clause in _clauses(s):
            for m in re.finditer(r"\b(PUT|DELETE|GET)\b[`\s]*\S*" + re.escape(_RATIO_PATH), clause):
                # "Never send DELETE ..." does not give the call.
                if not _NEGATION_BEFORE_RE.search(clause[: m.start()]):
                    methods.add(m.group(1))
    return methods


def check_ratio_raise_and_remove(text: str, **_: object) -> CheckResult:
    """For a reproducible slowness: raise the ratio with PUT, remove it with DELETE."""
    methods = _ratio_methods(text)
    missing = [m for m in ("PUT", "DELETE") if m not in methods]
    if missing:
        return False, (
            f"sampling ratio advice lacks {' and '.join(missing)} on "
            f"{_RATIO_PATH} (found: {sorted(methods) or 'none'})"
        )
    return True, "raises the sampling ratio with PUT and removes it with DELETE"


# A variable anywhere in a URL argument: `$VAR`, `${VAR}`, or `${VAR:-value}`.
# The third has a host when VAR is not set, so it needs no assignment.
_URL_VAR_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)(:-[^}]+)?\}|([A-Za-z_][A-Za-z0-9_]*))")
# An assignment read on the raw line, because shlex splits an unquoted `$(...)`
# value into several words: `export VAR=http://$(kubectl ... ):8000`.
_LINE_ASSIGN_RE = re.compile(r"^\s*(export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(\S+)")


def check_ratio_address_set(text: str, **_: object) -> CheckResult:
    """Every curl call on the ratio endpoint gets a host: a variable in its URL is set before it.

    A variable counts as set only by a command that does nothing else
    (`export VAR=value` or `VAR=value`), with a value, earlier in the fences.
    A prefix on the call itself (`VAR=value curl "$VAR/..."`) does not count:
    the shell expands `$VAR` before it applies the prefix. A literal URL or a
    `<placeholder>` passes, and so does `${VAR:-<url>}`, which falls back
    to a host when the variable is not set, and so does a plan that gives the calls in prose
    only, since it hands the operator no command that fails.
    """
    assigned: set[str] = set()
    unset: list[str] = []
    for line, commands in _shell_lines(text):
        first = commands[0] if commands else []
        words = first[1:] if first[:1] == ["export"] else first
        pairs = [_ASSIGN_RE.match(w) for w in words]
        if words and all(pairs):
            assigned.update(m.group(1) for m in pairs if m.group(2).strip("\"' "))
            continue
        # `export VAR=...`, or `VAR=...` on its own, sets the variable even when
        # shlex split a `$(...)` value into several words. `VAR=value cmd`
        # sets it for that one command only, so it does not count.
        m = _LINE_ASSIGN_RE.match(line)
        rest = _without_env_prefix(first)
        substituted = m and ("$(" in m.group(3) or "`" in m.group(3))
        if m and m.group(3).strip("\"'") and (m.group(1) or not rest or substituted):
            assigned.add(m.group(2))
            continue
        for cmd in commands:
            command = _without_env_prefix(cmd)
            if not command or not command[0].endswith("curl"):
                continue
            for tok in cmd:
                if "trace-sample-ratio" not in tok:
                    continue
                for v in _URL_VAR_RE.finditer(tok):
                    name = v.group(1) or v.group(3)
                    has_default = bool(v.group(2))
                    if name not in assigned and not has_default:
                        unset.append(name)
    if unset:
        return False, (
            f"ratio call uses ${sorted(set(unset))[0]} with no earlier line that sets it; "
            "the call fails in a shell where it is not set"
        )
    return True, "every ratio call has an address the plan sets or writes out"


_ASK_TOKEN_RE = re.compile(
    r"\b(paste|send|share|give|provide|type|enter|post|tell)\b.{0,60}\btoken\b.{0,60}"
    r"\b(me|here|chat|conversation|reply|message)\b"
    r"|\b(send|give|share|tell)\s+me\b.{0,60}\btoken\b"
    r"|\bwhat(\s+is|'s|’s)\s+your\b.{0,40}\btoken\b"
    r"|\b(i|we)\s+need\s+your\b.{0,40}\btoken\b",
    re.IGNORECASE,
)



# "Tell me when the token is saved in ~/.infrahub-admin-token." asks for no
# value: it asks whether the file route of rules/create-traces.md, step 5, is
# done. Only that status question is skipped: "Tell me the token in
# ~/.infrahub-admin-token" still asks for the value.
_TOKEN_IN_FILE_RE = re.compile(
    r"\b(when|once|after|if|whether)\b.{0,30}\btoken\b.{0,20}\b(is|has\s+been|was|are)\s+"
    r"(saved|stored|written|kept|put|in\s+place)\b",
    re.IGNORECASE,
)


def _asks_for_token(sentence: str) -> bool:
    """A clause of the sentence asks for the token value, with no negation before the ask."""
    for clause in _clauses(sentence):
        m = _ASK_TOKEN_RE.search(clause)
        if not m or _NEGATION_BEFORE_RE.search(clause[: m.start()]):
            continue
        if _TOKEN_IN_FILE_RE.search(clause):
            continue
        return True
    return False


# How the token reaches a command the agent runs (rules/create-traces.md,
# step 5). A variable exported in the operator's own terminal does not reach
# the agent's process, so "set it in your shell" alone is not a way. The three
# ways, strongest evidence first:
# 1. a command assigns the variable from a command substitution, such as
#    INFRAHUB_TRACES_API_TOKEN="$(cat ~/.infrahub-admin-token)";
# 2. the operator runs the command themselves;
# 3. the operator starts the agent session from the shell that exported it.
_TOKEN_VAR = "INFRAHUB_TRACES_API_TOKEN"
_RUN_YOURSELF_RE = re.compile(
    r"\brun\b.{0,40}\b(yourself|themselves|in your (own )?terminal)\b", re.IGNORECASE
)
# What the operator runs must be the collection itself. "Run this in your own
# terminal first" before an `export` fence is the own-shell advice that does
# not reach the agent's process.
_CREATE_OBJECT_RE = re.compile(
    r"infrahub-collect|\bcreate\b|\bcollect(ion)?\b|\bbundle\b", re.IGNORECASE
)
_START_AGENT_FROM_SHELL_RE = re.compile(
    r"\b(start|launch|open|restart)\w*\b.{0,60}\b(session|agent|assistant|claude)\b"
    r".{0,60}\b(shell|terminal)\b",
    re.IGNORECASE,
)


def _token_from_substitution(text: str) -> bool:
    """A command assigns the token variable from a command substitution."""
    for cmd in _shell_commands(text):
        for tok in cmd:
            name, sep, value = tok.partition("=")
            if sep and name.split()[-1:] == [_TOKEN_VAR] and ("$(" in value or "`" in value):
                return True
    return False


def _token_way_in_prose(text: str) -> bool:
    """A sentence tells the operator to run the command or start the agent from their shell."""
    for s in _sentences(_prose(text)):
        for clause in _clauses(s):
            for regex in (_RUN_YOURSELF_RE, _START_AGENT_FROM_SHELL_RE):
                m = regex.search(clause)
                if not m or _NEGATION_BEFORE_RE.search(clause[: m.start()]):
                    continue
                if regex is _RUN_YOURSELF_RE and not _CREATE_OBJECT_RE.search(clause):
                    continue
                return True
    return False


def check_token_env_not_asked(text: str, **_: object) -> CheckResult:
    """Never ask for the token value; say how INFRAHUB_TRACES_API_TOKEN reaches the command."""
    asks = [s for s in _sentences(_prose(text)) if _asks_for_token(s)]
    if asks:
        return False, f"asks for the token value in the conversation: {asks[0]!r}"
    if _TOKEN_VAR not in text:
        return False, f"does not name {_TOKEN_VAR}"
    if not (_token_from_substitution(text) or _token_way_in_prose(text)):
        return False, (
            f"does not say how {_TOKEN_VAR} reaches the command the agent runs "
            "(read from a file in the command, the operator runs it, or the agent "
            "session starts from the shell that exported it)"
        )
    return True, f"names {_TOKEN_VAR}, says how it reaches the command, and does not ask for the value"


_REVIEW_RE = re.compile(
    r"\b(review|check|inspect|read\s+through|look\s+(through|at|over))\b", re.IGNORECASE
)
_AFTER_SHARING_RE = re.compile(r"\bafter\b.{0,20}\b(shar|send|upload)", re.IGNORECASE)


def check_traces_review(text: str, **_: object) -> CheckResult:
    """With `--include-traces`, a review sentence names the traces (rules/review-before-sharing.md).

    The traces carry names from the operator's deployment, so the review step
    must name them: a review of "the bundle" alone does not. A prose sentence
    has a review verb with no negation before it in its clause, and names the
    traces after that verb, so "Review the bundle, including the traces."
    counts, while "You do not need to review the traces.", "The traces are
    readable." and "Review the traces after sharing." do not.
    """
    if not any("--include-traces" in _trace_options(o) for o in _create_options(text)):
        return True, "no traces command, so no traces review is needed"
    for s in _sentences(_prose(text)):
        if _AFTER_SHARING_RE.search(s):
            continue
        for clause in _clauses(s):
            m = _REVIEW_RE.search(clause)
            if not m or _NEGATION_BEFORE_RE.search(clause[: m.start()]):
                continue
            # The traces come after the verb, in its clause or in the rest of
            # the sentence: "Review the bundle, including the traces."
            if _TRACED_RE.search(s[s.find(clause) + m.end():]):
                return True, "asks the operator to review the traces before sharing"
    return False, "the review step does not name the traces (`bundle/traces/`)"


CHECKS: dict[str, CheckFn] = {
    "traces-review": check_traces_review,
    "traces-offered-with-window": check_traces_offered_with_window,
    "traces-not-offered": check_traces_not_offered,
    "ratio-raise-and-remove": check_ratio_raise_and_remove,
    "ratio-address-set": check_ratio_address_set,
    "sampling-caveat": check_sampling_caveat,
    "token-env-not-asked": check_token_env_not_asked,
    "mentions-create": check_mentions_create,
    "mentions-env-detect": check_mentions_env_detect,
    "mentions-flag": check_mentions_flag,
    "review-before-sharing": check_review_before_sharing,
    "cross-link-reporting-issues": check_cross_link_reporting_issues,
    "no-legacy-artifacts": check_no_legacy_artifacts,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the model's plan text; return skillgrade JSON."""
    text = output_path.read_text(errors="ignore") if output_path.exists() else ""
    entries: list[dict] = []
    passed_count = 0

    for spec in check_specs:
        name, kwargs = (spec if isinstance(spec, tuple) else (spec, {}))
        fn = CHECKS.get(name)
        if fn is None:
            entries.append({"name": name, "passed": False, "message": f"Unknown check: {name}"})
            continue
        try:
            ok, msg = fn(text, **kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        display = name if not kwargs else f"{name}({','.join(f'{k}={v}' for k, v in kwargs.items())})"
        entries.append({"name": display, "passed": ok, "message": msg})

    total = len(check_specs)
    score = round(passed_count / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed else f"All {total} checks passed."
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
