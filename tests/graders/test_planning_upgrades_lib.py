"""Tests for the upgrade plan checks in graders/planning-upgrades/lib.py.

Each of the four task graders runs against its four fixtures under
fixtures/planning-upgrades/<task>/: compliant, compliant variant, violating,
and violating near miss. The two compliant cases must score 1.0; the two
violating cases must score below 1.0 and fail on the check that grades the
rule, not on a neighbouring one.

The pass-variant fixtures for `read_only` and `evidence` carry the shapes a
live trial produced and the first draft of the checks rejected: a patch
roll-up hop (1.10.8 -> 1.10.10) before the minor hop, a bare `infrahub`
binary named in prose, and a backticked GraphQL query as evidence. They stay
here so a later tightening cannot bring those false fails back.

Fixtures are `.txt` so rumdl does not reformat them and the CLI invocation
gate does not flag the near miss, whose invented command is the point.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "planning-upgrades"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "planning-upgrades"

# Load lib.py by path under a unique name: the task graders import it as
# `lib`, which would collide with every other grader's lib.py in sys.modules.
_spec = importlib.util.spec_from_file_location(
    "planning_upgrades_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks = _mod.run_checks
CHECKS = _mod.CHECKS
check_no_mutating_commands = _mod.check_no_mutating_commands
check_verdict_has_evidence = _mod.check_verdict_has_evidence
check_finding_vocabulary = _mod.check_finding_vocabulary


# N-1 has no task of its own: the model planned sequential hops in six of six
# trials with no rule, so it is one line in SKILL.md rather than a rule. The
# check still runs as a neighbour in every other task grader, and these
# fixtures keep it honest.
_STANDALONE = {"sequential": [("sequential-hops", {"source": "1.6", "target": "1.9"})]}


def _task_checks(task: str) -> list:
    """The CHECKS list a task grader runs, read without importing the script."""
    if task in _STANDALONE:
        return _STANDALONE[task]
    tree = ast.parse((_GRADER_DIR / f"check_upgrade_path_{task}.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CHECKS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"check_upgrade_path_{task}.py defines no CHECKS")


def _failed(result: dict) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["passed"]]


# task -> the check name prefix each violating fixture must fail on.
# The sequential near miss has three hops and names every target minor, but
# each hop starts from 1.6, so a check that counts hops or collects targets
# passes it.
TASKS = {
    "sequential": {"fail": "sequential-hops", "fail-nearmiss": "sequential-hops"},
    "intermediate": {
        "fail": "every-hop-enumerated",
        "fail-nearmiss": "every-hop-enumerated",
    },
    "evidence": {"fail": "verdict-has-evidence", "fail-nearmiss": "verdict-has-evidence"},
    "read_only": {"fail": "no-mutating-commands", "fail-nearmiss": "no-mutating-commands"},
}


@pytest.mark.parametrize("task", sorted(TASKS))
@pytest.mark.parametrize("case", ["pass", "pass-variant"])
def test_compliant_fixture_scores_full(task, case):
    result = run_checks(_task_checks(task), _FIXTURES / task / f"{case}.txt")
    assert result["score"] == 1.0, _failed(result)


@pytest.mark.parametrize("task", sorted(TASKS))
@pytest.mark.parametrize("case", ["fail", "fail-nearmiss"])
def test_violating_fixture_fails_on_its_rule(task, case):
    result = run_checks(_task_checks(task), _FIXTURES / task / f"{case}.txt")
    failed = _failed(result)
    assert result["score"] < 1.0
    expected = TASKS[task][case]
    assert any(name.startswith(expected) for name in failed), failed


@pytest.mark.parametrize("task", sorted(TASKS))
def test_task_grader_names_only_registered_checks(task):
    for spec in _task_checks(task):
        name = spec[0] if isinstance(spec, tuple) else spec
        assert name in CHECKS, name


def test_missing_plan_scores_zero(tmp_path):
    result = run_checks(_task_checks("read_only"), tmp_path / "UPGRADE_PLAN.md")
    assert result["score"] < 1.0


_HEADER = (
    "| Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


def _plan(row: str, extra: str = "") -> str:
    return f"# Upgrade plan\n\n## 1.9 -> 1.10\n\n{_HEADER}{row}\n{extra}"


_ROW_YES = (
    "| node_metadata reserved | 1.10.0 | breaking | critical | before | {affected} "
    "| schemas/circuit.yml -> InfraCircuit.node_metadata | Rename the attribute "
    "| https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.10.0 |"
)


# The plan describes how; it never gives the upgrade command. Both directions:
# a plan with no commands passes, one handing over `infrahub upgrade` fails.


def test_plan_with_no_commands_is_read_only():
    ok, msg = check_no_mutating_commands(_plan(_ROW_YES.format(affected="yes")))
    assert ok, msg


@pytest.mark.parametrize(
    "command",
    [
        "docker compose exec infrahub-server infrahub upgrade",
        "kubectl exec deploy/infrahub-server -- infrahub upgrade",
    ],
)
def test_upgrade_command_handed_to_user_fails(command):
    text = _plan(_ROW_YES.format(affected="yes"), f"```bash\n{command}\n```\n")
    ok, msg = check_no_mutating_commands(text)
    assert not ok
    assert "upgrade command" in msg


def test_upgrade_check_probe_is_read_only():
    text = _plan(
        _ROW_YES.format(affected="yes"),
        "```bash\ndocker compose exec infrahub-server infrahub upgrade --check\n```\n",
    )
    ok, msg = check_no_mutating_commands(text)
    assert ok, msg


# A code span of prose that opens with the binary name is not an invocation,
# but a real subcommand in a code span still is.


def test_prose_code_span_naming_binary_is_not_an_invocation():
    text = _plan(_ROW_YES.format(affected="yes"), "Source: `infrahub GitHub releases, read 2026-09-26`\n")
    ok, msg = check_no_mutating_commands(text)
    assert ok, msg


def test_code_span_with_real_subcommand_is_still_graded():
    text = _plan(_ROW_YES.format(affected="yes"), "Then run `infrahub upgrade` on the server.\n")
    ok, _ = check_no_mutating_commands(text)
    assert not ok


# Emphasis in an enum cell is markup, not a different value; a value outside
# the enum still fails once the markup is stripped.


@pytest.mark.parametrize("affected", ["**yes**", "`yes`", "_yes_"])
def test_emphasised_enum_value_is_accepted(affected):
    text = _plan(_ROW_YES.format(affected=affected))
    ok, msg = check_verdict_has_evidence(text)
    assert ok, msg


def test_emphasised_non_enum_value_still_fails():
    text = _plan(_ROW_YES.format(affected="**probably**"))
    ok, _ = check_verdict_has_evidence(text)
    assert not ok


def test_emphasised_vocabulary_is_accepted():
    row = _ROW_YES.format(affected="yes").replace("| breaking | critical | before |", "| **breaking** | **critical** | **before** |")
    ok, msg = check_finding_vocabulary(_plan(row))
    assert ok, msg


# An unknown verdict resolved by searching the repo names a probe; one resolved
# by "review it" does not.

_ROW_UNKNOWN = (
    "| __ rejected in names | 1.9.7 | breaking | critical | before | unknown "
    "| Not visible from the excerpt | {action} "
    "| https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.9.7 |"
)


@pytest.mark.parametrize(
    "action",
    [
        "Run `grep -rn '__' schemas/` and rename every hit",
        "Grep your integration repositories for `APINodeSchema` and rename",
    ],
)
def test_unknown_resolved_by_repo_search_names_a_probe(action):
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


def test_unknown_resolved_by_review_names_no_probe():
    action = "Review your schema files for double underscores"
    ok, _ = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert not ok


# Change and Evidence cells quote what exists; the Action cell is a step. The
# same backticked command must pass in the first and fail in the second.

_ROW_GIT_AGENT = (
    "| `infrahub git-agent` removed | 1.11.0 | breaking | critical | before | yes "
    "| {evidence} | {action} "
    "| https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.11.0 |"
)


def test_command_quoted_as_evidence_is_not_handed_over():
    row = _ROW_GIT_AGENT.format(
        evidence="tasks.py runs `infrahub git-agent start`",
        action="Replace the call with the task worker",
    )
    ok, msg = check_no_mutating_commands(_plan(row))
    assert ok, msg


def test_command_in_action_cell_is_still_graded():
    row = _ROW_GIT_AGENT.format(
        evidence="tasks.py runs `infrahub git-agent start`",
        action="Run `infrahub upgrade` once the call is gone",
    )
    ok, _ = check_no_mutating_commands(_plan(row))
    assert not ok


@pytest.mark.parametrize(
    "evidence, expected",
    [
        ("Live read: 0 repositories, 0 generator definitions", True),
        ("The instance probably has no repositories", False),
    ],
)
def test_count_from_live_read_is_evidence(evidence, expected):
    row = _ROW_GIT_AGENT.format(evidence=evidence, action="None needed").replace("| yes |", "| no |")
    ok, _ = check_verdict_has_evidence(_plan(row))
    assert ok is expected
