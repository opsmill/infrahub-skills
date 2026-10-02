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


def test_missing_plan_fails_every_check_but_the_command_check(tmp_path):
    result = run_checks(_task_checks("read_only"), tmp_path / "UPGRADE_PLAN.md")
    # A missing plan shows no commands, which is the one thing it gets right.
    assert _failed(result) and "no-mutating-commands" not in _failed(result)
    assert len(_failed(result)) == len(result["checks"]) - 1


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


# A fenced block is offered to run and is held to the allowlist; a prose span
# may only name a command, and fails only when it names a write.


def test_prose_span_naming_a_removed_command_passes():
    text = _plan(_ROW_YES.format(affected="yes"), "1.11.0 removed `infrahub git-agent` entirely.\n")
    ok, msg = check_no_mutating_commands(text)
    assert ok, msg


def test_fenced_command_off_the_allowlist_fails():
    text = _plan(_ROW_YES.format(affected="yes"), "```bash\ninfrahub git-agent start\n```\n")
    ok, _ = check_no_mutating_commands(text)
    assert not ok


@pytest.mark.parametrize(
    "span",
    ["`infrahubctl schema load schemas/`", "`infrahubctl branch create test-upgrade`"],
)
def test_prose_span_naming_a_write_fails(span):
    text = _plan(_ROW_YES.format(affected="yes"), f"Then run {span} to try it.\n")
    ok, msg = check_no_mutating_commands(text)
    assert not ok
    assert "writes" in msg


# An unknown settled by reading a named file names a probe; "plan it" does not.


def test_unknown_resolved_by_reading_a_named_file_names_a_probe():
    action = "Read the image tags in `docker-compose.yml` and plan each service's bump"
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


def test_unknown_with_conditional_advice_names_no_probe():
    action = "If SSO is configured, leave the fallback on and have every user log in once"
    ok, _ = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert not ok


# A GraphQL query to run settles an unknown; a backticked setting name in the
# remedy does not, since it says what to change, not how to find out.


def test_unknown_resolved_by_a_graphql_query_names_a_probe():
    action = "Run `query { CoreWebhook { edges { node { name { value } } } } }` and set the attribute"
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


def test_unknown_with_only_a_setting_name_names_no_probe():
    action = "Leave `SSO_ACCOUNT_NAME_FALLBACK` on until every user has logged in"
    ok, _ = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert not ok


# An escaped pipe is part of the cell, not a boundary.


def test_escaped_pipe_stays_inside_the_action_cell():
    action = "Run `git diff main -- schemas/ \\| grep -n kind` and check each changed attribute"
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


def test_unescaped_pipe_still_splits_cells():
    rows = _mod.findings(_plan(_ROW_UNKNOWN.format(action="a | b")))
    assert rows[0]["action"] == "a"


def test_escaped_pipe_in_evidence_does_not_shift_the_action_cell():
    row = _ROW_GIT_AGENT.format(
        evidence="`grep -n git-agent tasks.py \\| head` hit line 2",
        action="Run `infrahub upgrade` afterwards",
    )
    ok, _ = check_no_mutating_commands(_plan(row))
    assert not ok


# Patches within one minor can be skipped: 1.9.1 -> 1.9.6 is one hop. A
# patch-only request that crosses into the next minor still fails.

check_sequential_hops = _mod.check_sequential_hops


def _hop_plan(heading: str) -> str:
    return f"# Upgrade plan\n\n## {heading}\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n"


def test_patch_upgrade_within_a_minor_is_one_hop():
    ok, msg = check_sequential_hops(_hop_plan("1.9.1 -> 1.9.6"), source="1.9.1", target="1.9.6")
    assert ok, msg


def test_patch_upgrade_that_crosses_a_minor_fails():
    ok, msg = check_sequential_hops(_hop_plan("1.9.1 -> 1.10.0"), source="1.9.1", target="1.9.6")
    assert not ok
    assert "crosses a minor" in msg


def test_minor_hop_from_an_older_patch_is_allowed():
    ok, msg = check_sequential_hops(_hop_plan("1.9.1 -> 1.10.0"), source="1.9.1", target="1.10.0")
    assert ok, msg


# --- Review findings on #159, each pinned both ways ------------------------


def _hop(body: str, heading: str = "1.10 -> 1.11") -> str:
    return f"# Upgrade plan\n\n## {heading}\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n{body}"


# An indented code block is a code block: the upgrade in one is handed over,
# and a read-only probe in one is fine.


def test_indented_block_handing_over_the_upgrade_fails():
    ok, _ = check_no_mutating_commands(_hop("Run the upgrade:\n\n    docker compose exec infrahub-server infrahub upgrade\n"))
    assert not ok


def test_indented_block_with_a_probe_passes():
    ok, msg = check_no_mutating_commands(_hop("Check first:\n\n    docker compose exec infrahub-server infrahub upgrade --check\n"))
    assert ok, msg


def test_indented_fence_inside_a_list_item_is_graded():
    body = "1. Upgrade:\n\n   ```bash\n   docker compose exec infrahub-server infrahub upgrade\n   ```\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


def test_nested_list_item_is_not_a_code_block():
    body = "- Step\n\n    - Upgrade infrahub to 1.11 following the guide\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


# `-n infrahub` is an option value; the real binary comes after `--`.


def test_kubectl_namespace_does_not_hide_a_write():
    body = "```bash\nkubectl exec -n infrahub deploy/infrahub-server -- infrahub db migrate\n```\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


def test_kubectl_namespace_does_not_fail_a_probe():
    body = "```bash\nkubectl exec -n infrahub infrahub-server-0 -- infrahub upgrade --check\n```\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


def test_compose_service_named_infrahub_is_skipped():
    body = "```bash\ndocker compose exec infrahub infrahub upgrade\n```\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


# A fence's backticks do not shift inline-span pairing in the prose after it.


def test_prose_after_a_fence_is_not_read_as_code():
    body = "```bash\ninfrahubctl info\n```\n\nAfter `1.11.0` lands, the infrahub upgrade step follows the guide, see `docs`.\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


def test_inline_upgrade_after_a_fence_is_still_graded():
    body = "```bash\ninfrahubctl info\n```\n\nThen run `infrahub upgrade`.\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


# A product name is not evidence, and the bare binary name is not a probe.


@pytest.mark.parametrize(
    "evidence",
    ["See the GitHub release notes", "Affects every infrahub deployment", "PostgreSQL is upgraded"],
)
def test_product_names_are_not_evidence(evidence):
    row = _ROW_GIT_AGENT.format(evidence=evidence, action="Fix it")
    ok, _ = check_verdict_has_evidence(_plan(row))
    assert not ok


@pytest.mark.parametrize(
    "evidence",
    ["`CoreStandardGroup` inherits it", "InfraCircuit.node_metadata", "`infrahubctl info` reported 1.10.8"],
)
def test_named_kinds_and_probes_are_evidence(evidence):
    row = _ROW_GIT_AGENT.format(evidence=evidence, action="Fix it")
    ok, msg = check_verdict_has_evidence(_plan(row))
    assert ok, msg


def test_asking_an_admin_names_no_probe():
    ok, _ = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action="Check with your infrahub admin")))
    assert not ok


def test_a_read_only_probe_resolves_an_unknown():
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action="Run infrahub db showmigrations on the server")))
    assert ok, msg


# A `v` prefix is a version.


def test_v_prefixed_hop_headings_parse():
    ok, msg = check_sequential_hops(_hop("", heading="v1.10 -> v1.11"), source="1.10", target="1.11")
    assert ok, msg


def test_v_prefixed_release_cell_counts():
    row = _ROW_GIT_AGENT.format(evidence="`tasks.py`", action="Fix it").replace("| 1.11.0 |", "| v1.11.0 |")
    ok, msg = _mod.check_every_hop_enumerated(_plan(row).replace("1.9 -> 1.10", "1.10 -> 1.11"), releases="1.11.0")
    assert ok, msg


def test_v_prefixed_skip_still_fails():
    ok, _ = check_sequential_hops(_hop("", heading="v1.8 -> v1.11"), source="1.8", target="1.11")
    assert not ok


# An overview heading spanning the whole range is not a hop.

_FIVE_HOPS = "".join(f"## 1.{i} -> 1.{i + 1}\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n" for i in range(5, 10))


def test_overview_heading_is_not_a_hop():
    text = "# Plan\n\n## Overview: 1.5.2 -> 1.10.0\n\nFive hops.\n\n" + _FIVE_HOPS
    ok, msg = check_sequential_hops(text, source="1.5", target="1.10")
    assert ok, msg


def test_single_consolidated_hop_still_fails():
    text = f"# Plan\n\n## 1.5.2 -> 1.10.0\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n"
    ok, _ = check_sequential_hops(text, source="1.5", target="1.10")
    assert not ok


# Crossing a major, and a target older than the source.


def test_crossing_into_the_next_major_is_one_hop():
    ok, msg = check_sequential_hops(_hop("", heading="1.11 -> 2.0"), source="1.11", target="2.0")
    assert ok, msg


def test_skipping_the_first_minor_of_a_new_major_fails():
    ok, _ = check_sequential_hops(_hop("", heading="1.11 -> 2.1"), source="1.11", target="2.1")
    assert not ok


def test_target_older_than_source_fails_with_its_own_message():
    ok, msg = check_sequential_hops(_hop("", heading="1.9 -> 1.10"), source="1.10", target="1.9")
    assert not ok
    assert "older than source" in msg


# Bold table headers are the same columns.


def test_bold_headers_are_parsed():
    header = _HEADER.replace("| Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |",
                             "| **Change** | **Release** | **Kind** | **Severity** | **When** | **Affected** | **Evidence** | **Action** | **Source** |")
    text = f"# Plan\n\n## 1.10 -> 1.11\n\n{header}{_ROW_YES.format(affected='yes')}\n"
    ok, msg = check_verdict_has_evidence(text)
    assert ok, msg


def test_bold_headers_still_catch_a_bad_verdict():
    header = _HEADER.replace("| Affected |", "| **Affected** |")
    text = f"# Plan\n\n## 1.10 -> 1.11\n\n{header}{_ROW_YES.format(affected='probably')}\n"
    ok, _ = check_verdict_has_evidence(text)
    assert not ok


# A backticked command in the Action is a runnable probe; a backticked package
# name is not.


def test_backticked_shell_command_resolves_an_unknown():
    action = "Run `pip show infrahub-sdk` where the generators run, then move it with the server"
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


def test_backticked_package_name_is_not_a_probe():
    action = "Pin `infrahub-sdk` to 1.19.0 or later in the dependency file"
    ok, _ = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert not ok


# Decided on #159: the plan never writes the upgrade command, even to say it
# was not run. The `--check` probe is the only form allowed.


def test_saying_the_upgrade_command_was_not_run_still_fails():
    ok, _ = check_no_mutating_commands(_hop("I did not run `infrahub upgrade`; the plan is below.\n"))
    assert not ok


def test_saying_the_upgrade_was_not_run_passes():
    ok, msg = check_no_mutating_commands(_hop("I did not run the upgrade; the plan is below.\n"))
    assert ok, msg


# A write command named bare in prose is a name (a release note quoting it); one
# carrying its target, or one that runs bare, is a handover.


def test_prose_naming_a_write_command_bare_passes():
    body = "1.11.0 keeps `pyarrow` in the `object-transfer` extra for `infrahubctl object load`.\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


@pytest.mark.parametrize(
    "span",
    ["`infrahubctl object load objects/`", "`infrahubctl branch create test-upgrade`", "`infrahub db migrate`"],
)
def test_prose_write_with_a_target_or_runnable_bare_fails(span):
    ok, msg = check_no_mutating_commands(_hop(f"Then run {span} to check.\n"))
    assert not ok
    assert "writes" in msg


# --- Review on #159 (BeArchiTek), each reproduction pinned both ways --------


@pytest.mark.parametrize(
    "body",
    [
        "```bash\ndocker compose exec infrahub-server infrahub upgrade \\\n  --rebase-branches\n```\n",
        "```bash\nkubectl exec deploy/x -- sh -c \"infrahub upgrade\"\n```\n",
        "```bash\nsudo -E infrahub upgrade\n```\n",
        "Then run `infrahubctl object delete InfraDevice spine1`.\n",
        "```bash\ninfrahub upgrade --rebase-branches 'unterminated\n```\n",
    ],
    ids=["continuation", "sh-c", "sudo-E", "object-delete", "unparseable"],
)
def test_handed_over_writes_fail(body):
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


@pytest.mark.parametrize(
    "body",
    [
        "```bash\nVERSION=1.11.0 docker compose run --rm --no-deps infrahub-server \\\n  infrahub upgrade --check\n```\n",
        "```bash\nkubectl exec deploy/x -- sh -c \"infrahub db showmigrations\"\n```\n",
        "Your compose file still starts the agent:\n\n```yaml\nservices:\n  agent:\n    command: infrahub git-agent start --debug\n```\n",
    ],
    ids=["continued-probe", "sh-c-probe", "yaml-quote"],
)
def test_probes_and_quoted_files_pass(body):
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


def test_writes_come_from_the_cli_tree():
    for path in [("infrahubctl", "object", "delete"), ("infrahubctl", "object", "update"), ("infrahubctl", "object", "create")]:
        assert path in _mod.WRITE_INVOCATIONS


# A title naming the whole range is not a second hop, and patch roll-ups around
# a hop do not turn the hop into an "overview".


def test_title_with_the_same_range_as_the_only_hop_passes():
    text = f"# Plan\n\n## Upgrade plan: 1.9.2 to 1.10.0\n\nSummary.\n\n## 1.9 -> 1.10\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n"
    ok, msg = check_sequential_hops(text, source="1.9", target="1.10")
    assert ok, msg


def test_patch_rollups_around_a_hop_pass():
    body = f"{_HEADER}{_ROW_YES.format(affected='yes')}\n"
    text = f"# Plan\n\n## 1.9.1 -> 1.9.6\n\n{body}\n## 1.9 -> 1.10\n\n{body}\n## 1.10.0 -> 1.10.3\n\n{body}"
    ok, msg = check_sequential_hops(text, source="1.9", target="1.10")
    assert ok, msg


def test_title_does_not_hide_a_skipped_minor():
    text = f"# Plan\n\n## Upgrade plan: 1.8.2 to 1.10.0\n\n## 1.8 -> 1.10\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n"
    ok, _ = check_sequential_hops(text, source="1.8", target="1.10")
    assert not ok


# `infrahub db migrate --check` and `--plan` report without applying; plain
# `infrahub db migrate` applies.


@pytest.mark.parametrize("flag", ["--check", "--plan"])
def test_db_migrate_report_flags_are_probes(flag):
    for body in (f"Then `infrahub db migrate {flag}` lists what is pending.\n", f"```bash\ninfrahub db migrate {flag}\n```\n"):
        ok, msg = check_no_mutating_commands(_hop(body))
        assert ok, msg


def test_db_migrate_without_a_report_flag_fails():
    for body in ("Then run `infrahub db migrate`.\n", "```bash\ninfrahub db migrate\n```\n"):
        ok, _ = check_no_mutating_commands(_hop(body))
        assert not ok


def test_db_migrate_plan_resolves_an_unknown():
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action="Run infrahub db migrate --plan in the target image")))
    assert ok, msg


# --- Second review round on #159 (BeArchiTek) -------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "kubectl exec deploy/x -- bash -l -c 'infrahub upgrade'",
        "sh -e -c \"infrahub upgrade\"",
        "ssh prod 'docker compose exec infrahub-server infrahub upgrade'",
    ],
    ids=["bash-l-c", "sh-e-c", "ssh"],
)
def test_quoted_command_behind_any_wrapper_is_graded(line):
    ok, _ = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert not ok


def test_quoted_probe_behind_ssh_passes():
    body = "```bash\nssh prod 'VERSION=1.11.0 docker compose run --rm --no-deps infrahub-server infrahub upgrade --check'\n```\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


@pytest.mark.parametrize("lang", ["text", "markdown", "yaml"])
def test_upgrade_handed_over_in_a_non_shell_fence_fails(lang):
    body = f"```{lang}\ndocker compose exec infrahub-server infrahub upgrade\n```\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


def test_non_shell_fence_with_other_commands_still_passes():
    body = "```text\nDatabase needs to be updated (v69 -> v71), 2 migrations pending\ninfrahub git-agent start --debug\n```\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


def test_overview_summary_table_is_not_graded_as_findings():
    summary = "| Hop | Notes |\n| --- | --- |\n| 1.6 -> 1.7 | see below |\n"
    bad_summary = f"{_HEADER}| Roll-up | 1.6.0–1.9.0 | breaking | big | soon | maybe | lots | review | x |\n"
    hops = "".join(f"## 1.{i} -> 1.{i + 1}\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n" for i in range(6, 9))
    text = f"# Plan\n\n## Overview: 1.6.0 -> 1.9.0\n\n{summary}\n{bad_summary}\n{hops}"
    for check in (check_verdict_has_evidence, check_finding_vocabulary):
        ok, msg = check(text)
        assert ok, msg
    assert all(r["_hop"] != "Overview: 1.6.0 -> 1.9.0" for r in _mod.findings(text))


def test_single_hop_section_rows_are_still_graded():
    text = f"# Plan\n\n## 1.6 -> 1.7\n\n{_HEADER}{_ROW_YES.format(affected='probably')}\n"
    ok, _ = check_verdict_has_evidence(text)
    assert not ok



# --- cubic review on #159 ----------------------------------------------------


def test_tilde_fenced_example_headings_are_not_hops():
    example = "~~~markdown\n## 1.3 -> 1.4\n~~~\n"
    text = f"# Plan\n\n## 1.9 -> 1.10\n\n{_HEADER}{_ROW_YES.format(affected='yes')}\n{example}"
    ok, msg = check_sequential_hops(text, source="1.9", target="1.10")
    assert ok, msg


@pytest.mark.parametrize("action", ["Then `review the repo` before the window", "See `the release notes` and decide"])
def test_backticked_prose_is_not_a_probe(action):
    ok, _ = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert not ok


@pytest.mark.parametrize(
    "action",
    [
        "Run `pip show infrahub-sdk` where the generators run",
        "Run `git diff main -- schemas/` and check each changed attribute",
        "Run `kubectl get pods -n infrahub` to read the image tags",
    ],
)
def test_read_only_inspection_commands_are_probes(action):
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


@pytest.mark.parametrize(
    "line",
    ["infrahub migrate", "infrahub data restore", "kubectl exec deploy/x -- infrahub migrate", "infrahubctl frobnicate"],
)
def test_invented_command_in_a_code_block_fails(line):
    ok, msg = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert not ok
    assert "not a real command" in msg


@pytest.mark.parametrize(
    "line",
    [
        "kubectl exec -n infrahub infrahub-server-0 -- bash",
        "docker compose exec infrahub infrahub upgrade --check",
        "kubectl exec -n infrahub infrahub-server-0 -- infrahub upgrade --check",
    ],
)
def test_wrapper_words_are_not_invented_commands(line):
    ok, msg = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert ok, msg


def test_invented_command_named_in_prose_is_not_graded():
    ok, msg = check_no_mutating_commands(_hop("Older plans name `infrahub migrate`, which never existed.\n"))
    assert ok, msg


# --- Third review round on #159 (BeArchiTek): command position --------------


@pytest.mark.parametrize(
    "line",
    [
        "docker compose exec infrahub bash",
        'docker compose exec infrahub sh -c "infrahub upgrade --check"',
        'echo "back up infrahub before the window"',
        'git commit -m "pin infrahub to 1.11"',
    ],
    ids=["exec-service-bash", "exec-service-sh-c-probe", "echo", "git-commit"],
)
def test_binary_outside_command_position_is_not_a_call(line):
    ok, msg = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert ok, msg


def test_list_continuation_prose_is_not_a_code_block():
    body = "1. Take the hop.\n\n    infrahub stays on 1.10 until the window opens.\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


def test_code_block_inside_a_list_item_is_still_graded():
    body = "1. Take the hop.\n\n       docker compose exec infrahub-server infrahub upgrade\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


@pytest.mark.parametrize(
    "line",
    ["sudo -E infrahub migrate", "docker compose run --rm infrahub migrate", "env FOO=1 infrahub migrate"],
    ids=["sudo-E", "compose-run-service-binary", "env"],
)
def test_invented_command_behind_a_wrapper_fails(line):
    ok, msg = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert not ok
    assert "not a real command" in msg


@pytest.mark.parametrize(
    "action",
    ["Read the target's `upgrade --check` count line", "Run `docker compose ps` to read the image tags"],
)
def test_bare_probe_forms_resolve_an_unknown(action):
    ok, msg = check_verdict_has_evidence(_plan(_ROW_UNKNOWN.format(action=action)))
    assert ok, msg


# --- cubic, round 3: wrapper options and the `--` terminator ---------------


@pytest.mark.parametrize(
    "line",
    [
        "uv run --group test infrahub upgrade",
        "sudo --user root infrahub upgrade",
        "sudo -- infrahub upgrade",
        "env --chdir /srv infrahub upgrade",
        "docker compose exec infrahub -- infrahub upgrade",
    ],
    ids=["uv-group", "sudo-long-user", "sudo-terminator", "env-long-chdir", "compose-terminator-upgrade"],
)
def test_upgrade_behind_wrapper_options_fails(line):
    ok, _ = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert not ok


@pytest.mark.parametrize(
    "line",
    [
        "uv run --group test infrahubctl info",
        "sudo --user root infrahubctl info",
        "sudo -- infrahubctl info",
        "docker compose exec infrahub -- infrahubctl version",
        "docker compose exec infrahub -it infrahubctl version",
    ],
    ids=["uv-group", "sudo-long-user", "sudo-terminator", "compose-terminator", "compose-flag-after-service"],
)
def test_probe_behind_wrapper_options_passes(line):
    ok, msg = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert ok, msg


# --- /code-review round on #159, plus cubic on run-wrapper options ----------


@pytest.mark.parametrize(
    "line",
    [
        "docker-compose exec infrahub-server infrahub upgrade",
        "docker container exec srv infrahub upgrade",
        "podman exec srv infrahub upgrade",
        "timeout 600 infrahub upgrade",
        "nice -n 5 infrahub upgrade",
        "uvx infrahubctl schema load s/",
        "pipx run infrahubctl schema load s/",
        "kubectl exec pod infrahub upgrade",
        "poetry -C /srv run infrahub upgrade",
        "pdm -p /srv run infrahub upgrade",
        "uv --directory /srv run infrahub upgrade",
        "watch -n 5 infrahub upgrade",
    ],
)
def test_upgrade_or_write_behind_any_wrapper_fails(line):
    ok, _ = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert not ok


@pytest.mark.parametrize(
    "line",
    [
        "docker-compose run --rm infrahub-server infrahub upgrade --check",
        "podman exec srv infrahub db showmigrations",
        "timeout 600 infrahubctl info",
        "uvx infrahubctl info",
        "poetry -C /srv run infrahubctl info",
        "kubectl exec pod infrahubctl version",
    ],
)
def test_probe_behind_any_wrapper_passes(line):
    ok, msg = check_no_mutating_commands(_hop(f"```bash\n{line}\n```\n"))
    assert ok, msg


@pytest.mark.parametrize(
    "span",
    ["`infrahub db update-core-schema`", "`infrahub db init`", "`infrahub db reset`", "`infrahub recover`"],
)
def test_server_write_named_in_prose_fails(span):
    ok, _ = check_no_mutating_commands(_hop(f"Then run {span} on the server.\n"))
    assert not ok


def test_server_read_only_named_in_prose_passes():
    body = "1.4.11 added `infrahub db check-duplicate-schema-fields`, and `infrahub db showmigrations` came in 1.10.0.\n"
    ok, msg = check_no_mutating_commands(_hop(body))
    assert ok, msg


def test_linked_release_is_one_release():
    row = _ROW_YES.format(affected="yes").replace(
        "| 1.10.0 |", "| [1.10.0](https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.10.0) |", 1
    )
    ok, msg = _mod.check_every_hop_enumerated(_plan(row), releases="1.10.0")
    assert ok, msg


def test_linked_range_is_still_a_range():
    row = _ROW_YES.format(affected="yes").replace("| 1.10.0 |", "| [1.9.0](x)–[1.10.0](y) |", 1)
    ok, _ = _mod.check_every_hop_enumerated(_plan(row))
    assert not ok


def test_rollback_section_is_not_a_hop():
    body = f"{_HEADER}{_ROW_YES.format(affected='yes')}\n"
    text = f"# Plan\n\n## 1.9 -> 1.10\n\n{body}\n## Rollback: 1.10.0 -> 1.9.2\n\nRestore the backup.\n"
    ok, msg = check_sequential_hops(text, source="1.9", target="1.10")
    assert ok, msg


def test_heading_note_with_another_version_does_not_move_the_target():
    ok, msg = check_sequential_hops(_hop("", heading="1.9 -> 1.10 (requires Neo4j 5.26)"), source="1.9", target="1.10")
    assert ok, msg


def test_heading_skip_is_still_caught_with_a_note():
    ok, _ = check_sequential_hops(_hop("", heading="1.8 -> 1.10 (requires Neo4j 5.26)"), source="1.8", target="1.10")
    assert not ok


def test_fence_with_an_info_string_does_not_close_a_fence():
    body = "```\nAn example plan:\n```bash\necho hi\n```\n\n```bash\ndocker compose exec infrahub-server infrahub upgrade\n```\n"
    ok, _ = check_no_mutating_commands(_hop(body))
    assert not ok


@pytest.mark.parametrize("evidence", ["See GitHub.com release notes", "Docs.infrahub explain it"])
def test_domain_names_are_not_kind_attribute_evidence(evidence):
    row = _ROW_GIT_AGENT.format(evidence=evidence, action="Fix it")
    ok, _ = check_verdict_has_evidence(_plan(row))
    assert not ok


def test_kind_attribute_evidence_still_counts():
    row = _ROW_GIT_AGENT.format(evidence="InfraCircuit.node_metadata", action="Fix it")
    ok, msg = check_verdict_has_evidence(_plan(row))
    assert ok, msg
