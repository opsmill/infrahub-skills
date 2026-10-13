"""Tests for the moves-source-branch-commit check in managing-checks (#194).

A proposed change runs its checks with the repository commit recorded on its
source branch. On a branch synced with Git, `infrahubctl branch rebase` and
`CoreProposedChangeRunCheck` leave that commit where it is, so the check
passes only a script that merges main into each source branch's Git branch
and pushes it. A Git rebase onto main does not count: it rewrites the branch,
so a plain push is rejected, and after a force-push the repository sync
cannot pull the branch. A new branch and proposed change do not count
either: a branch cut from main carries none of the old branch's data.

The four fixtures under fixtures/managing-checks/proposed-change-commit/ are
compliant, compliant variant, violating, and violating near miss, plus two
more violating ones for the routes the rule does not accept. Each violating
fixture is the compliant one with one shape changed: the violating one swaps
the Git step for the runbook's rebase, the near miss keeps every token the
check reads (checkout, merge, push, the loop variable, the default branch)
but binds them to the wrong subject, merging the source branch into main and
pushing main, fail-rebase swaps the merge for a Git rebase and a force-push,
and fail-new-branch swaps the Git step for a new branch and proposed change.
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
_FAIL_PREFIX = "No `git push` to a source branch after merging main into it"


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


def test_rebase_fixture_fails_because_it_rebases():
    result = _run_fixture("fail-rebase")
    assert result["score"] < 1.0
    (entry,) = result["checks"]
    assert entry["message"].startswith(_FAIL_PREFIX)
    assert "git push destinations: $b" in entry["message"]
    assert "branches rebased onto main, which the sync cannot pull: $b" in entry["message"]


def test_new_branch_fixture_fails_because_it_moves_no_branch():
    result = _run_fixture("fail-new-branch")
    assert result["score"] < 1.0
    (entry,) = result["checks"]
    assert entry["message"].startswith(_FAIL_PREFIX)
    assert "git push destinations: none" in entry["message"]
    assert "branches main was merged into: none" in entry["message"]


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
        (
            'while read -r b; do git checkout "$b"; git merge origin/main; git push origin "$b"; '
            "done < f",
            True,
        ),
        (
            'push_one() { git checkout "$1"; git merge origin/main; '
            'git push origin "HEAD:refs/heads/$1"; }',
            True,
        ),
        (
            'b=$(jq -r .branch pc.json)\ngit checkout "$b"\ngit merge origin/main\n'
            'git push origin "$b"',
            True,
        ),
        (
            'FIX=fix-power-budget\ngit checkout "$FIX"\ngit merge origin/main\n'
            'git push origin "$FIX"',
            False,
        ),
        ('git checkout "$UNSET_BRANCH"\ngit merge origin/main\ngit push origin "$UNSET_BRANCH"',
         False),
        ("git checkout '<branch>'\ngit merge origin/main\ngit push origin '<branch>'", False),
        ("git checkout fix-power-budget\ngit merge origin/main\ngit push origin fix-power-budget",
         False),
    ],
    ids=["read-var", "function-arg", "assigned-from-command", "literal-var", "unbound-var",
         "placeholder", "literal"],
)
def test_push_destination_must_be_a_bound_branch_variable(script, expected):
    assert _passes(script) is expected



# The merge has to land on the branch that is pushed. Merging main into main,
# or into nothing the script checked out, and then pushing a source branch
# leaves that branch at its old commit.
@pytest.mark.parametrize(
    ("script", "expected"),
    [
        (
            'git checkout "$b"\ngit merge origin/main\ngit push origin "$b"',
            True,
        ),
        (
            'git checkout -b tmp "origin/$b"\ngit merge origin/main\n'
            'git push origin "tmp:refs/heads/${b}"',
            True,
        ),
        ('git clone --branch "$b" "$URL" w\ngit -C w pull origin main\ngit -C w push origin HEAD',
         True),
        ('git checkout main\ngit merge origin/main\ngit push origin "$b"', False),
        ('git checkout "$b"\ngit checkout main\ngit merge origin/main\ngit push origin "$b"',
         False),
        ('git clone "$URL" w\ngit -C w merge origin/main\ngit -C w push origin "$b"', False),
        ('git merge origin/main\ngit push origin "$b"', False),
    ],
    ids=["checkout-merge-push", "temp-branch-to-source", "clone-branch-pull", "merged-on-main", "switched-back-to-main",
         "clone-default-branch", "no-checkout"],
)
def test_merge_must_land_on_the_pushed_branch(script, expected):
    looped = f"while read -r b; do\n{script}\ndone < branches.txt"
    assert _passes(looped) is expected

# A Git rebase onto main rewrites the source branch: a plain push is rejected,
# and after a force-push the repository sync cannot pull the branch. It counts
# as no merge, whatever comes before or after it on that branch.
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('  git pull --no-rebase origin main\n  git push origin "$b"', True),
        ('  git pull --rebase=false origin main\n  git push origin "$b"', True),
        ('  git rebase origin/main\n  git push origin "$b"', False),
        ('  git rebase origin/main\n  git push --force origin "$b"', False),
        ('  git pull --rebase origin main\n  git push origin "$b"', False),
        ('  git pull -r origin main\n  git push origin "$b"', False),
        ('  git merge origin/main\n  git rebase origin/main\n  git push origin "$b"', False),
        ('  git rebase origin/main\n  git merge origin/main\n  git push origin "$b"', False),
    ],
    ids=["pull-no-rebase", "pull-rebase-false", "rebase-push", "rebase-force-push",
         "pull-rebase", "pull-r", "merge-then-rebase", "rebase-then-merge"],
)
def test_rebase_onto_main_does_not_count(body, expected):
    assert _passes(_LOOP.format(body=body)) is expected


def test_rebase_with_branch_argument_does_not_count():
    script = 'while read -r b; do\ngit rebase origin/main "$b"\ngit push origin "$b"\ndone < f'
    assert not _passes(script)


# A new branch cut from main has none of the old branch's data or commits, so
# opening one with a new proposed change re-validates main, not the change.
def test_new_branch_and_proposed_change_do_not_count():
    script = """
for b in $(list_branches); do
  uv run infrahubctl branch create "${b}-v2"
  curl -sS "$INFRAHUB_ADDRESS/graphql" -d @- <<EOF
{"query": "mutation { CoreProposedChangeCreate(data: {name: {value: \\"$b\\"}}) { ok } }"}
EOF
done
"""
    assert not _passes(script)


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
    assert _mod._BRANCH_REBASE in tree.GROUPS[_mod._BRANCH_GROUP]
