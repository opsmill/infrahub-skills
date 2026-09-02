"""Tests for graders/common/lib.py and graders/common/cli_tree.py.

The cases are the answer shapes a correct model actually produces, plus the
invented-command shapes the rules exist to remove. Both halves matter: a
check that fails the best possible answer is as broken as one that passes a
wrong one.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMON = _REPO_ROOT / "graders" / "common"
sys.path.insert(0, str(_COMMON))

_spec = importlib.util.spec_from_file_location("common_graders_lib", _COMMON / "lib.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_cli_commands_exist = _mod.check_cli_commands_exist
check_python_transform_dry_run = _mod.check_python_transform_dry_run
check_preflight_write_probe = _mod.check_preflight_write_probe
check_generator_target_is_key_value = _mod.check_generator_target_is_key_value


# --- cli-commands-exist --------------------------------------------------

CLI_ACCEPTED = [
    pytest.param("Run `infrahubctl info` first.", id="real-leaf"),
    pytest.param("Run `infrahubctl schema check schemas/`.", id="real-group-sub"),
    pytest.param(
        "The `infrahubctl` CLI is fine. Name the transform `spine_config`.",
        id="two-spans-are-not-one-command",
    ),
    pytest.param(
        "```bash\n# infrahubctl reads the token from the environment\n"  # cli-check: ignore
        "infrahubctl info\n```",
        id="comment-inside-a-fence-is-prose",
    ),
    pytest.param(
        "Run `infrahubctl generator create_dc site=hq`.",
        id="snake-case-name-is-not-a-verb",
    ),
]


@pytest.mark.parametrize("text", CLI_ACCEPTED)
def test_cli_commands_exist_accepts(text):
    ok, msg = check_cli_commands_exist(text)
    assert ok, msg


# These are the invented forms the check exists to reject, so the fixtures
# have to spell them out. cli-check: ignore
CLI_REJECTED = [
    pytest.param("", id="empty-output"),
    pytest.param("A plan with no commands in it at all.", id="names-no-command"),
    pytest.param("```\ninfrahubctl check run my_check\n```", id="invented-run"),  # cli-check: ignore
    pytest.param("Run `infrahubctl schema validate schemas/`.", id="invented-group-sub"),  # cli-check: ignore
    pytest.param("Run `infrahubctl generator list`.", id="invented-list"),  # cli-check: ignore
]


@pytest.mark.parametrize("text", CLI_REJECTED)
def test_cli_commands_exist_rejects(text):
    ok, _ = check_cli_commands_exist(text)
    assert not ok


def test_empty_output_is_not_a_free_pass():
    """A run that produced nothing must not score half the task."""
    assert check_cli_commands_exist("")[0] is False


# --- python-transform-dry-run --------------------------------------------


def test_render_named_as_the_wrong_command_is_accepted():
    """The task's own expectations ask for exactly this phrasing."""
    ok, msg = check_python_transform_dry_run(
        "Use `infrahubctl transform spine_config device=spine1`, not "
        "`infrahubctl render spine_config`, because render only resolves "
        "jinja2_transforms.",
        "spine_config",
    )
    assert ok, msg


def test_render_recommended_is_rejected():
    ok, _ = check_python_transform_dry_run(
        "Run `infrahubctl transform spine_config x=y`. "
        "Also `infrahubctl render spine_config` works.",
        "spine_config",
    )
    assert not ok


def test_transform_name_is_a_parameter():
    ok, msg = check_python_transform_dry_run(
        "Run `infrahubctl transform rack-report site=hq`.", "rack_report"
    )
    assert ok, msg


# --- preflight-write-probe -----------------------------------------------


def test_the_rules_own_negation_does_not_trip_the_antipattern_guard():
    ok, msg = check_preflight_write_probe(
        "Probe it: `infrahubctl branch create preflight-probe-a1` then "
        "`infrahubctl branch delete preflight-probe-a1`. A green "
        "`infrahubctl info` does not confirm the token is valid, because "
        "reads are served anonymously."
    )
    assert ok, msg


def test_treating_info_as_clearance_fails():
    ok, _ = check_preflight_write_probe(
        "Your green `infrahubctl info` confirms the token is valid, so you are "
        "good to go. Run `infrahubctl branch create x` and `branch delete x`."
    )
    assert not ok


def test_listing_branches_is_not_a_write_probe():
    ok, _ = check_preflight_write_probe(
        "Run `infrahubctl branch list`. Reads are served anonymously, so a "
        "green result does not prove write access."
    )
    assert not ok


# --- generator-target-is-key-value ---------------------------------------


def test_key_value_target_on_a_branch_passes():
    ok, msg = check_generator_target_is_key_value(
        "Run `infrahubctl generator create_dc site_id=1809d0bc --branch dry-run`."
    )
    assert ok, msg


def test_bare_id_target_fails():
    """A bare token is dropped, and the run then writes the whole group."""
    ok, _ = check_generator_target_is_key_value(
        "Run `infrahubctl generator create_dc 1809d0bc --branch dry-run`."
    )
    assert not ok


def test_missing_branch_fails():
    ok, _ = check_generator_target_is_key_value(
        "Run `infrahubctl generator create_dc site_id=1809d0bc`."
    )
    assert not ok


# --- one tree, two consumers ---------------------------------------------


def test_the_guard_script_and_the_grader_read_the_same_tree():
    """Two copies would let a CLI bump pass CI and leave the evals stale."""
    script_path = _REPO_ROOT / "scripts" / "check-cli-invocations.py"
    spec = importlib.util.spec_from_file_location("cli_guard", script_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)

    import cli_tree

    assert Path(guard.cli_tree.__file__).resolve() == Path(cli_tree.__file__).resolve()
    assert guard.cli_tree.GROUPS == cli_tree.GROUPS
    assert guard.cli_tree.LEAVES == cli_tree.LEAVES
    assert guard.SDK_VERSION == cli_tree.SDK_VERSION
    # And the grader reaches the tree through the same module.
    assert _mod.invalid_invocations.__module__ == cli_tree.__name__
