"""Tests for the moves-source-branch-commit check in managing-checks (#194).

A proposed change runs its checks with the repository commit recorded on its
source branch. On a branch synced with Git, `infrahubctl branch rebase` and
`CoreProposedChangeRunCheck` leave that commit where it is, so the check
passes only a script that pushes main into each source branch's Git branch,
or one that opens a new branch and proposed change.

The four fixtures under fixtures/managing-checks/proposed-change-commit/ are
compliant, compliant variant, violating, and violating near miss. Each
violating fixture is the compliant one with one shape changed: the violating
one swaps the Git step for the runbook's rebase, and the near miss keeps every
token the check reads (checkout, merge, push, the loop variable, the default
branch) but binds them to the wrong subject, merging the source branch into
main and pushing main.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "managing-checks"
_FIXTURES = (
    Path(__file__).resolve().parent / "fixtures" / "managing-checks" / "proposed-change-commit"
)

_spec = importlib.util.spec_from_file_location(
    "managing_checks_lib_pc_commit", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check = _mod.check_moves_source_branch_commit
_FAIL_PREFIX = "No `git push` to a source branch after merging or rebasing main into it"


def _task_checks() -> list[str]:
    """The CHECKS list the task grader runs, read without importing the script."""
    tree = ast.parse((_GRADER_DIR / "check_proposed_change_commit.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CHECKS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("check_proposed_change_commit.py defines no CHECKS")


def _run_fixture(case: str) -> dict:
    return _mod.run_checks(
        _task_checks(),
        _FIXTURES / "absent-output.yml",
        sh_path=_FIXTURES / f"{case}.sh",
    )


def _passes(script: str) -> bool:
    return check(None, sh_raw=script)[0]


def test_task_grader_runs_the_check():
    assert "moves-source-branch-commit" in _task_checks()
    assert _mod.CHECKS["moves-source-branch-commit"] is check


# --- The four fixtures ------------------------------------------------------


@pytest.mark.parametrize("case", ["pass", "pass-variant"])
def test_compliant_fixtures_score_one(case):
    result = _run_fixture(case)
    assert result["score"] == 1.0, result


def test_violating_fixture_fails_with_no_push():
    result = _run_fixture("fail")
    assert result["score"] < 1.0
    (entry,) = result["checks"]
    assert entry["name"] == "moves-source-branch-commit"
    assert entry["message"].startswith(_FAIL_PREFIX)
    assert "git push destinations: none" in entry["message"]
    assert "infrahubctl branch rebase calls: 1" in entry["message"]


def test_near_miss_fails_because_it_pushes_main():
    result = _run_fixture("fail-nearmiss")
    assert result["score"] < 1.0
    (entry,) = result["checks"]
    assert entry["message"].startswith(_FAIL_PREFIX)
    assert "git push destinations: $DEFAULT_BRANCH" in entry["message"]


def test_missing_script_fails_closed():
    ok, msg = check(None, sh_raw="")
    assert not ok
    assert "output.sh" in msg


# --- Boundaries: one case on each side --------------------------------------

_LOOP = """
for b in $(list_branches); do
  git checkout "$b"
{body}
done
"""


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('  git merge --no-edit origin/main\n  git push origin "$b"', True),
        ('  git push origin "$b"\n  git merge --no-edit origin/main', False),
    ],
    ids=["merge-then-push", "push-then-merge"],
)
def test_merge_must_precede_the_push(body, expected):
    assert _passes(_LOOP.format(body=body)) is expected


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("origin/main", True),
        ("refs/remotes/origin/main", True),
        ('"origin/${BASE:-main}"', True),
        ("origin/fix-power-budget", False),
        ("origin/main-backup", False),
    ],
)
def test_merge_source_must_be_the_default_branch(ref, expected):
    body = f'  git merge --no-edit {ref}\n  git push origin "$b"'
    assert _passes(_LOOP.format(body=body)) is expected


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ('while read -r b; do git merge origin/main; git push origin "$b"; done < f', True),
        ('push_one() { git merge origin/main; git push origin "HEAD:refs/heads/$1"; }', True),
        ('b=$(jq -r .branch pc.json)\ngit merge origin/main\ngit push origin "$b"', True),
        ('FIX=fix-power-budget\ngit merge origin/main\ngit push origin "$FIX"', False),
        ('git merge origin/main\ngit push origin "$UNSET_BRANCH"', False),
        ("git merge origin/main\ngit push origin '<branch>'", False),
        ("git merge origin/main\ngit push origin fix-power-budget", False),
    ],
    ids=["read-var", "function-arg", "assigned-from-command", "literal-var", "unbound-var",
         "placeholder", "literal"],
)
def test_push_destination_must_be_a_bound_branch_variable(script, expected):
    assert _passes(script) is expected


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        (
            'infrahubctl branch create "$b-v2"\n'
            "curl -d '{\"query\": \"mutation { CoreProposedChangeCreate(data: {}) { ok } }\"}' x",
            True,
        ),
        (
            "curl -d '{\"query\": \"mutation { CoreProposedChangeCreate(data: {}) { ok } }\"}' x\n"
            'infrahubctl branch create "$b-v2"',
            False,
        ),
    ],
    ids=["branch-then-proposed-change", "proposed-change-then-branch"],
)
def test_new_branch_route_needs_the_branch_first(script, expected):
    assert _passes(script) is expected


def test_new_branch_route_reads_heredoc_graphql():
    script = """
for b in $(list_branches); do
  uv run infrahubctl branch create "${b}-v2"
  curl -sS "$INFRAHUB_ADDRESS/graphql" -d @- <<EOF
{"query": "mutation { CoreProposedChangeCreate(data: {name: {value: \\"$b\\"}}) { ok } }"}
EOF
done
"""
    assert _passes(script)


# --- Shell reading (dev/guidelines/graders.md) ------------------------------


def test_comments_and_echoed_text_are_not_commands():
    script = """
# git merge origin/main && git push origin "$b"
for b in $BRANCHES; do
  echo "run: git merge origin/main; git push origin $b"
  printf '%s\\n' "git push origin $b"
  infrahubctl branch rebase "$b"
done
"""
    assert not _passes(script)


def test_git_global_options_and_wrappers_are_peeled():
    body = (
        '  git -C "$DIR" -c core.editor=true merge origin/main\n'
        '  sudo -u deploy env GIT_SSH_COMMAND=ssh git -C "$DIR" push origin "$b"'
    )
    assert _passes(_LOOP.format(body=body))


def test_git_stash_push_is_not_a_push():
    body = '  git merge origin/main\n  git stash push "$b"'
    assert not _passes(_LOOP.format(body=body))


def test_continuations_join_lines():
    body = '  git merge \\\n    --no-edit \\\n    origin/main\n  git push \\\n    origin "$b"'
    assert _passes(_LOOP.format(body=body))


def test_push_to_head_follows_the_checked_out_branch():
    script = """
while read -r b; do
  git switch "$b" && git pull --no-rebase origin main && git push origin HEAD
done < branches.txt
"""
    assert _passes(script)


def test_every_fence_is_graded_including_indented_and_long_fences():
    answer = """Here is the script.

1. First the part from the runbook:

   ```bash
   infrahubctl branch rebase "$b"
   ```

2. Then the part that moves the commit:

   ````bash
   for b in $BRANCHES; do
     git checkout "$b"
     git merge --no-edit origin/main
     git push origin "$b"
   done
   ````
"""
    assert _passes(answer)


def test_cli_tree_is_the_source_of_infrahubctl_commands():
    tree = _mod._cli_tree
    assert _mod._BRANCH_CREATE in tree.GROUPS[_mod._BRANCH_GROUP]
    assert _mod._BRANCH_REBASE in tree.GROUPS[_mod._BRANCH_GROUP]
