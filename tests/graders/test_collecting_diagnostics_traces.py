"""Tests for the trace checks in graders/collecting-diagnostics/lib.py.

Each task grader runs against four fixtures under
fixtures/collecting-diagnostics/<task>/: compliant, compliant variant,
violating, and violating near miss. The two compliant cases must score 1.0;
the two violating cases must score below 1.0 and fail on the check that grades
rules/create-traces.md, not on a neighbouring one.

What each near miss guards against:

- traces_slowness: the full command with a window, a question about something
  else, and "traces?" only in a shell comment. A check that looks for any
  question, or reads comments, passes it.
  fail-nearmiss-since asks first, but uses `--traces-since` for a slowness
  that has ended; a check that accepts either window form passes it (cubic
  review of #234).
  fail-min-duration gives the window but leaves out `--traces-min-duration`,
  which the rule asks for in every traces command (BeArchiTek review of
  #234). fail-min-duration-nearmiss names the option in prose and in a
  shell comment only; a check that matches the option name anywhere in the
  plan passes it.
  fail-caveat and fail-caveat-nearmiss grade the sampling caveat instead: the
  near miss says "no sampling" in prose and "only a share" in a shell comment
  only. A check that matches the word "sampling", or reads comments, passes it
  (cubic review of #234).
- traces_reproducible: PUT and GET on the ratio endpoint, and "delete" in
  prose about the bundle folder. A check that matches the endpoint name or the
  word "delete" passes it.
  fail-nearmiss-negation gives DELETE only in a negated sentence ("Never send
  DELETE ..."); fail-nearmiss-path calls /api/trace-sample-ratio, not the
  /api/troubleshooting/ endpoint. A check that ignores negation, or matches
  only the last path segment, passes them (cubic review of #234).
  fail-address grades the address instead: the calls use $INFRAHUB_ADDRESS
  and no line sets it, so they fail in a shell without it (manual test of
  the skill). fail-address-nearmiss sets it only as a prefix of each call,
  which the shell applies after it expands $INFRAHUB_ADDRESS, and says "Set
  INFRAHUB_ADDRESS" in prose; fail-address-nearmiss-order exports it after
  the calls. A check that looks for any assignment passes them.
  pass-address-variant writes one URL out and sets the variable with a bare
  assignment in another fence, used as ${INFRAHUB_ADDRESS}.
  pass-address-default uses ${INFRAHUB_ADDRESS:-http://localhost:8000},
  which has a host when the variable is not set. Trials with the old rule
  wrote this form; a check that rejects any variable fails it.
- traces_no_terminal: names INFRAHUB_TRACES_API_TOKEN, but asks the operator
  to paste the token. A check that only looks for the variable passes it.
  fail-nearmiss-negation puts a "not" after the request ("Paste the token
  here; I will not log it."). A check that skips any sentence with a negation
  passes it (review of #234). fail-nearmiss-own-shell names the variable and
  asks for nothing, but only says "set it in your own shell", which does not
  reach a command the agent runs; pass-prose-ways gives the two ways that live
  in prose only, with no command substitution (cubic review of #234).
- basic_workflow: no trace option in any command, but a question that offers
  traces. A check that reads only the commands passes it.
  pass-stack-trace asks about a stack trace in the logs, which offers no
  traces. A check that matches any question with "trace" fails it (review
  of #234).

The compliant fixture of traces_slowness wraps its question over two lines,
which a line-by-line sentence split read as no question.

Fixtures are `.txt` so rumdl does not reformat them.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "collecting-diagnostics"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collecting-diagnostics"

# Load lib.py by path under a unique name: the task graders import it as
# `lib`, which would collide with every other grader's lib.py in sys.modules.
_spec = importlib.util.spec_from_file_location(
    "collecting_diagnostics_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks = _mod.run_checks


def _task_checks(task: str) -> list:
    """The CHECKS list a task grader runs, read without importing the script."""
    tree = ast.parse((_GRADER_DIR / f"check_{task}.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CHECKS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"check_{task}.py defines no CHECKS")


def _failed(result: dict) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["passed"]]


# task -> the check each violating fixture must fail on.
TASKS = {
    "traces_slowness": "traces-offered-with-window(window=absolute)",
    "traces_reproducible": "ratio-raise-and-remove",
    "traces_no_terminal": "token-env-not-asked",
    "basic_workflow": "traces-not-offered",
}


# Violating fixtures that grade a second check of the task, by name prefix.
OTHER_CHECKS = {
    ("traces_slowness", "fail-caveat"): "sampling-caveat",
    ("traces_reproducible", "fail-address"): "ratio-address-set",
}


def _expected_failure(task: str, fixture: str) -> str:
    for (t, prefix), check in OTHER_CHECKS.items():
        if t == task and fixture.startswith(prefix):
            return check
    return TASKS[task]


def _fixtures(prefix: str) -> list[tuple[str, str]]:
    """Every (task, fixture) pair whose file name starts with the prefix.

    The four required fixtures are named pass, pass-variant, fail and
    fail-nearmiss; a review can add more under the same prefixes.
    """
    pairs = [
        (task, f.stem)
        for task in sorted(TASKS)
        for f in sorted((_FIXTURES / task).glob(f"{prefix}*.txt"))
    ]
    for task in TASKS:
        assert any(t == task for t, _ in pairs), f"{task} has no {prefix} fixture"
    return pairs


@pytest.mark.parametrize(("task", "fixture"), _fixtures("pass"))
def test_compliant_fixture_scores_full(task: str, fixture: str) -> None:
    result = run_checks(_task_checks(task), _FIXTURES / task / f"{fixture}.txt")
    assert result["score"] == 1.0, result["details"]


@pytest.mark.parametrize(("task", "fixture"), _fixtures("fail"))
def test_violating_fixture_fails_on_the_rule(task: str, fixture: str) -> None:
    result = run_checks(_task_checks(task), _FIXTURES / task / f"{fixture}.txt")
    assert result["score"] < 1.0, result["details"]
    assert _failed(result) == [_expected_failure(task, fixture)], result["details"]


def test_token_from_substitution_accepts_a_token_that_starts_with_equals() -> None:
    """A shell token such as `=foo` has an empty name before the `=`.

    `name.split()[-1]` raised IndexError on it (cubic review of #234).
    """
    text = "```bash\necho =foo\n```\n"
    assert _mod._token_from_substitution(text) is False


@pytest.mark.parametrize(
    "sentence",
    [
        "Tell me your super_admin token.",
        "What's your token?",
        "What’s your super_admin token?",
        "I need your super_admin token to run the command.",
        "Paste the token here.",
    ],
)
def test_asks_for_token_matches_a_request(sentence: str) -> None:
    assert _mod._asks_for_token(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "Do not tell me your token.",
        "Never paste the token in this conversation.",
        "Save your super_admin token in ~/.infrahub-admin-token.",
        "The command asks for the token without showing it.",
    ],
)
def test_asks_for_token_ignores_other_sentences(sentence: str) -> None:
    assert not _mod._asks_for_token(sentence)


_DELETE = 'curl -X DELETE "${INFRAHUB_ADDRESS:-http://localhost:8000}/api/troubleshooting/trace-sample-ratio"'


@pytest.mark.parametrize(
    "plan",
    [
        # A `console` block with a shell prompt in front of the command.
        f"```console\n$ {_DELETE}\n```\n",
        # A block opened and closed with four backticks.
        f"````bash\n{_DELETE}\n````\n",
        # A block with a tilde fence, inside a list item.
        f"1. Run:\n\n   ~~~bash\n   {_DELETE}\n   ~~~\n",
    ],
)
def test_shell_commands_reads_the_call(plan: str) -> None:
    """The parser finds the curl call whatever the block format.

    A trial whose agent summary showed this call scored "no curl call", and
    these two formats were the ones the parser missed.
    """
    commands = _mod._shell_commands(plan)
    assert [c[:3] for c in commands] == [["curl", "-X", "DELETE"]], commands


def test_shell_commands_keeps_a_dollar_variable_at_line_start() -> None:
    """Only `$ ` with a space is a prompt; `$VAR` at the start of a line is not."""
    commands = _mod._shell_commands('```bash\n"$CURL" -X DELETE "$INFRAHUB_ADDRESS/x"\n```\n')
    assert commands == [["$CURL", "-X", "DELETE", "$INFRAHUB_ADDRESS/x"]], commands


def test_four_backtick_fence_holds_a_three_backtick_line() -> None:
    """A four-backtick block ends only at four backticks, not at a ``` line inside it."""
    plan = "````markdown\n```bash\ninfrahub-collect create\n```\n````\n\nAfter the block.\n"
    assert _mod._fenced_blocks(plan) == ["```bash\ninfrahub-collect create\n```\n"]
    assert "After the block." in _mod._prose(plan)
