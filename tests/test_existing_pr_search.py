"""Run the existing-PR search snippet against a stub `gh` and check what it finds.

Both entrance stages of the skill-change pipeline, `analyzing-skill-bugs` and
`grilling-skill-features`, search for a pull request that already covers the
change before they analyse or design it. Before this test, every PR lookup in
the pipeline searched only its own branch (`gh pr list --head "$BRANCH"`), so a
PR on any other branch was invisible and the same change was built twice.

The search lives once, as the first `bash` block under
`## Searching for existing pull requests` in
`.agents/skills/skill-pipeline-common/handoff-format.md`. This test runs that
block, not a copy of it, so what is tested is what the agent runs.

The contract the block has to meet:

- It takes `ISSUE` (an issue number, or empty) and `TARGETS` (space-separated
  path prefixes) from `ISSUE="<...>"` and `TARGETS="<...>"` lines, which this
  test replaces with its own values.
- It prints one line per matching PR, starting with `#<number>`.
- A PR matches when it is open, or merged with a merge commit that is not an
  ancestor of `HEAD`, and it either closes `ISSUE`, names `#ISSUE` as a whole
  token in its title or body, or changes a file under one of `TARGETS`.
  Closed, unmerged PRs never match.
- It does not fetch.

The stub `gh` emulates `gh pr list` the way GitHub answers it: it returns the
fixture PRs for the requested `--state`, honours `--limit` and a
`merged:>=<date>` term in `--search`, ignores every other search term and
`--head`, and applies `--jq` with `jq -r`. A block that leans on a GitHub
text search to do the matching therefore prints the near misses and fails.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess  # noqa: S404

import pytest

ROOT = Path(__file__).resolve().parent.parent
HANDOFF_FORMAT = (
    ROOT / ".agents" / "skills" / "skill-pipeline-common" / "handoff-format.md"
)
SECTION = "## Searching for existing pull requests"
NOT_IN_HEAD = "0123456789abcdef0123456789abcdef01234567"

STUB_GH = r"""#!/usr/bin/env python3
import json, os, re, subprocess, sys

args = sys.argv[1:]
if args[:2] != ["pr", "list"]:
    sys.exit(f"stub gh: only 'gh pr list' is supported, got {args!r}")
if os.environ.get("FAKE_GH_FAIL"):
    sys.exit("stub gh: HTTP 401: Bad credentials")
state, jq, limit, search = "open", None, 30, ""
for i, arg in enumerate(args):
    if arg == "--state":
        state = args[i + 1]
    elif arg.startswith("--state="):
        state = arg.split("=", 1)[1]
    elif arg in ("--jq", "-q"):
        jq = args[i + 1]
    elif arg.startswith("--jq="):
        jq = arg.split("=", 1)[1]
    elif arg in ("--limit", "-L"):
        limit = int(args[i + 1])
    elif arg.startswith("--limit="):
        limit = int(arg.split("=", 1)[1])
    elif arg in ("--search", "-S"):
        search = args[i + 1]
prs = json.load(open(os.environ["FAKE_GH_FIXTURES"]))
prs = [p for p in prs if state == "all" or p["state"].lower() == state]
since = re.search(r"merged:>=(\S+)", search)
if since:
    prs = [p for p in prs if (p.get("mergedAt") or "")[:10] >= since.group(1)]
prs = prs[:limit]
payload = json.dumps(prs)
if jq is None:
    print(payload)
else:
    sys.exit(subprocess.run(["jq", "-r", jq], input=payload, text=True).returncode)
"""


def _pr(
    number: int,
    state: str,
    *,
    title: str = "chore: unrelated",
    body: str = "",
    closes: tuple[int, ...] = (),
    files: tuple[str, ...] = ("README.md",),
    merge_commit: str | None = None,
    merged_at: str = "2099-01-01T00:00:00Z",
    base: str = "main",
) -> dict:
    return {
        "number": number,
        "state": state,
        "title": title,
        "body": body,
        "headRefName": f"someone/branch-{number}",
        "closingIssuesReferences": [{"number": n} for n in closes],
        "files": [{"path": f} for f in files],
        "mergeCommit": {"oid": merge_commit} if merge_commit else None,
        "mergedAt": merged_at if state == "MERGED" else None,
        "baseRefName": base,
    }


def _fixtures(head_sha: str, filler: int = 0, extra: tuple = ()) -> list[dict]:
    # gh lists newest first. Filler PRs match nothing and sit ahead of the
    # real fixtures, so a block that stops at one page never reaches them.
    newer = [_pr(1000 + n, "OPEN") for n in range(filler)]
    newer += [_pr(2000 + n, "MERGED", merge_commit=head_sha) for n in range(filler)]
    return (
        newer
        + list(extra)
        + [
            # Open, on another branch, closes #25: the PR the own-branch lookup misses.
            _pr(201, "OPEN", title="fix(menus): removing items", closes=(25,)),
            # Open, the body digits contain 25 but no #25 token.
            _pr(202, "OPEN", body="Bumps the limit from 25 to 50, see #250 and #1255."),
            # Open, no issue, changes a file under the menus skill.
            _pr(
                203,
                "OPEN",
                title="fix(menus): icons",
                files=("skills/infrahub-managing-menus/rules/menu-icons.md",),
            ),
            # Open, #25 followed by letters is not the #25 token.
            _pr(
                208, "OPEN", body="Tracked under #25abc and #25_old in the old tracker."
            ),
            # Open, names #25 in the body without closing it.
            _pr(204, "OPEN", body="Follow-up to #25, which this partly addresses."),
            # Open, the body names a range that ends at #177, not #25.
            _pr(205, "OPEN", body="Harvest review lessons from #142-#177."),
            # Open, a path that only starts like the target.
            _pr(206, "OPEN", files=("skills/infrahub-managing-menus-extra/SKILL.md",)),
            # Closed, not merged, closes #25: never a match.
            _pr(
                207,
                "CLOSED",
                closes=(25,),
                files=("skills/infrahub-managing-menus/SKILL.md",),
            ),
            # Merged after HEAD, closes #25: the fix exists but the tree lacks it.
            _pr(301, "MERGED", closes=(25,), merge_commit=NOT_IN_HEAD),
            # Merged and already in HEAD, closes #25: nothing to warn about.
            _pr(
                302,
                "MERGED",
                closes=(25,),
                merge_commit=head_sha,
                files=("skills/infrahub-managing-menus/SKILL.md",),
            ),
            # Merged after HEAD, unrelated.
            _pr(303, "MERGED", merge_commit=NOT_IN_HEAD),
        ]
    )


def _block() -> str:
    text = HANDOFF_FORMAT.read_text()
    start = text.find(SECTION + "\n")
    assert start != -1, (
        f"{HANDOFF_FORMAT.relative_to(ROOT)} has no {SECTION!r} section, so neither "
        "entrance stage searches for a pull request on another branch"
    )
    rest = text[start + len(SECTION) :]
    next_heading = re.search(r"^## ", rest, re.M)
    section = rest[: next_heading.start()] if next_heading else rest
    match = re.search(r"```bash\n(.*?)```", section, re.S)
    assert match, f"{SECTION!r} has no bash block"
    return match.group(1)


def _execute(
    tmp_path: Path,
    issue: str,
    targets: str,
    *,
    filler: int = 0,
    extra: tuple = (),
    gh_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
    if shutil.which("jq") is None:
        pytest.fail("jq is required to emulate gh --jq; install it")
    block = _block()
    for name in ("ISSUE", "TARGETS"):
        assert re.search(rf"^\s*{name}=", block, re.M), (
            f'the block must take {name} from a {name}="<...>" line'
        )
    block = re.sub(r"^\s*(ISSUE|TARGETS)=.*$", "", block, flags=re.M)

    repo = tmp_path / "repo"
    repo.mkdir()
    git = [
        "git",
        "-C",
        str(repo),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
    ]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "base"], check=True)
    head = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    # A checkout with a known default branch, as the entrance stages have.
    subprocess.run([*git, "update-ref", "refs/remotes/origin/main", head], check=True)
    subprocess.run(
        [*git, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"],
        check=True,
    )

    fixtures = tmp_path / "prs.json"
    fixtures.write_text(json.dumps(_fixtures(head, filler, extra)))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(STUB_GH)
    gh.chmod(0o755)
    script = tmp_path / "search.sh"
    script.write_text(block)

    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path),
        "ISSUE": issue,
        "TARGETS": targets,
        "FAKE_GH_FIXTURES": str(fixtures),
    }
    if gh_fails:
        env["FAKE_GH_FAIL"] = "1"
    return subprocess.run(
        ["bash", str(script)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _run(
    tmp_path: Path, issue: str, targets: str, *, filler: int = 0, extra: tuple = ()
) -> set[int]:
    result = _execute(tmp_path, issue, targets, filler=filler, extra=extra)
    assert result.returncode == 0, f"the block failed:\n{result.stderr}"
    return {int(m) for m in re.findall(r"^#(\d+)\b", result.stdout, re.M)}


@pytest.mark.parametrize(
    ("issue", "targets", "expected"),
    [
        pytest.param(
            "25",
            "skills/infrahub-managing-checks/",
            {201, 204, 301},
            id="issue-match-on-other-branches",
        ),
        # Part A runs at key derivation, before the stage knows any target.
        pytest.param("25", "", {201, 204, 301}, id="issue-match-before-targets-known"),
        pytest.param(
            "",
            "skills/infrahub-managing-menus/",
            {203},
            id="file-overlap-without-issue",
        ),
        pytest.param(
            "25",
            "skills/infrahub-managing-menus/ scripts/check-symlinks.py",
            {201, 203, 204, 301},
            id="issue-and-file-overlap",
        ),
        pytest.param("999", "skills/infrahub-managing-checks/", set(), id="no-match"),
    ],
)
def test_search_prints_exactly_the_matching_prs(
    tmp_path: Path, issue: str, targets: str, expected: set[int]
) -> None:
    """The block prints every matching PR and none of the near misses.

    Near misses that must not print: digits containing 25 (#202), #25 with
    a letter or underscore suffix (#208), a range
    ending at another number (#205), a path that only starts like the target
    (#206), a closed PR (#207), a merge already in HEAD (#302), and an
    unrelated merge (#303).
    """
    assert _run(tmp_path, issue, targets) == expected


def test_search_reads_past_the_first_page(tmp_path: Path) -> None:
    """A match older than the newest page of PRs is still found.

    150 open and 150 merged PRs that match nothing sit ahead of the real
    fixtures. A block that stops at a fixed `--limit` never reaches #201,
    #204 or #301, and would record `none found` for a PR that exists.
    """
    assert _run(tmp_path, "25", "skills/infrahub-managing-checks/", filler=150) == {
        201,
        204,
        301,
    }


def test_search_fails_loudly_when_gh_fails(tmp_path: Path) -> None:
    """A failed `gh` call is an error, not an empty result.

    Printing nothing on failure reads exactly like "no matching PR", so the
    stage would record `none found` without having searched.
    """
    result = _execute(tmp_path, "25", "", gh_fails=True)
    assert result.returncode != 0, "the block exited 0 although gh failed"
    assert "SEARCH FAILED" in result.stdout + result.stderr, (
        "the block must say SEARCH FAILED so the stage does not record none found"
    )


def test_search_fails_loudly_when_jq_fails(tmp_path: Path) -> None:
    """A jq error while matching is an error, not an empty result.

    The match runs inside a pipeline whose last command is a `while` loop, so
    a jq failure upstream of it used to leave exit status 0 with nothing
    printed. A PR whose `files` is null makes the file match fail.
    """
    broken = _pr(209, "OPEN")
    broken["files"] = None
    result = _execute(tmp_path, "", "skills/infrahub-managing-checks/", extra=(broken,))
    assert result.returncode != 0, "the block exited 0 although jq failed"
    assert "SEARCH FAILED" in result.stdout + result.stderr, (
        "the block must say SEARCH FAILED so the stage does not record none found"
    )


def test_search_keeps_old_prs_merged_into_another_branch(tmp_path: Path) -> None:
    """A PR merged into a non-default branch, long ago, is still a candidate.

    Narrowing merged PRs to those merged since this branch's base commit
    assumes every older merge landed on the default branch. #304 was merged
    into another branch years before the base commit, so it is not in HEAD,
    and a date cutoff drops it before the ancestry check ever sees it.
    """
    old_elsewhere = _pr(
        304,
        "MERGED",
        closes=(25,),
        merge_commit=NOT_IN_HEAD,
        merged_at="2020-01-01T00:00:00Z",
        base="feature/long-running",
    )
    assert _run(
        tmp_path, "25", "skills/infrahub-managing-checks/", extra=(old_elsewhere,)
    ) == {201, 204, 301, 304}
