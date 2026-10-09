"""Run the existing-PR search against a stub `gh` and check what it finds.

Both entrance stages of the skill-change pipeline, `analyzing-skill-bugs` and
`grilling-skill-features`, search for a pull request that already covers the
change before they analyse or design it. Before this search, every PR lookup in
the pipeline searched only its own branch (`gh pr list --head "$BRANCH"`), so a
PR on any other branch was invisible and the same change was built twice.

The search is `.agents/skills/skill-pipeline-common/scripts/find_existing_prs.py`,
which `handoff-format.md` § "Searching for existing pull requests" tells the
stages to run. Its docstring is the contract; this test runs the script, not a
copy of its logic, in a temporary git checkout with a stub `gh` first on
`PATH`.

The stub answers the way GitHub does, including the parts that caused misses:

- `gh pr list` returns the fixture PRs for `--state`, honours `--limit` and a
  `merged:>=<date>` term in `--search`, ignores other search terms, and cuts
  each PR's `files` to 100 while `changedFiles` keeps the true count.
- `gh api --paginate repos/{owner}/{repo}/pulls/<n>/files` returns every file.
- `FAKE_GH_FAIL` makes every call fail, like a lost token.

A search that leans on a GitHub text search, stops at one page, narrows merged
PRs by date, or trusts the first 100 files therefore misses a fixture or prints
a near miss, and fails here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess  # noqa: S404
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
COMMON = ROOT / ".agents" / "skills" / "skill-pipeline-common"
SCRIPT = COMMON / "scripts" / "find_existing_prs.py"
HANDOFF_FORMAT = COMMON / "handoff-format.md"
SECTION = "## Searching for existing pull requests"
NOT_IN_HEAD = "0123456789abcdef0123456789abcdef01234567"

STUB_GH = r"""#!/usr/bin/env python3
import json, os, re, sys

if os.environ.get("FAKE_GH_FAIL"):
    sys.exit("stub gh: HTTP 401: Bad credentials")
args = sys.argv[1:]
prs = json.load(open(os.environ["FAKE_GH_FIXTURES"]))

if args[:1] == ["api"]:
    number = int(re.search(r"pulls/(\d+)/files", " ".join(args)).group(1))
    pr = next(p for p in prs if p["number"] == number)
    print("\n".join(f["path"] for f in pr["files"]))
    sys.exit(0)

if args[:2] != ["pr", "list"]:
    sys.exit(f"stub gh: unsupported call {args!r}")
state, limit, search = "open", 30, ""
for i, arg in enumerate(args):
    if arg == "--state":
        state = args[i + 1]
    elif arg in ("--limit", "-L"):
        limit = int(args[i + 1])
    elif arg in ("--search", "-S"):
        search = args[i + 1]
prs = [p for p in prs if state == "all" or p["state"].lower() == state]
since = re.search(r"merged:>=(\S+)", search)
if since:
    prs = [p for p in prs if (p.get("mergedAt") or "")[:10] >= since.group(1)]
listed = []
for p in prs[:limit]:
    p = dict(p)
    if p["files"] is not None:
        p["changedFiles"] = len(p["files"])
        p["files"] = p["files"][:100]
    listed.append(p)
print(json.dumps(listed))
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


def _fixtures(
    head_sha: str, ahead_sha: str, filler: int = 0, extra: tuple = ()
) -> list[dict]:
    # gh lists newest first. Filler PRs match nothing and sit ahead of the
    # real fixtures, so a search that stops at one page never reaches them.
    newer = [_pr(1000 + n, "OPEN") for n in range(filler)]
    newer += [_pr(2000 + n, "MERGED", merge_commit=head_sha) for n in range(filler)]
    return [
        *newer,
        *extra,
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
        _pr(208, "OPEN", body="Tracked under #25abc and #25_old in the old tracker."),
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
        # Merged on origin/main, which is fetched but ahead of HEAD: the clone
        # has the merge commit, and it is still not in HEAD.
        _pr(305, "MERGED", closes=(25,), merge_commit=ahead_sha),
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


def _execute(
    tmp_path: Path,
    issue: str,
    targets: str,
    *,
    filler: int = 0,
    extra: tuple = (),
    gh_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
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
    # A checkout whose fetched origin/main is one commit ahead of HEAD, as a
    # stage working on a branch cut before the latest merge has.
    ahead = subprocess.run(
        [*git, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", "merge"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run([*git, "update-ref", "refs/remotes/origin/main", ahead], check=True)
    subprocess.run(
        [*git, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"],
        check=True,
    )

    fixtures = tmp_path / "prs.json"
    fixtures.write_text(json.dumps(_fixtures(head, ahead, filler, extra)))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(STUB_GH)
    gh.chmod(0o755)

    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path),
        "FAKE_GH_FIXTURES": str(fixtures),
    }
    if gh_fails:
        env["FAKE_GH_FAIL"] = "1"
    args = [sys.executable, str(SCRIPT)]
    if issue:
        args += ["--issue", issue]
    for target in targets.split():
        args += ["--target", target]
    return subprocess.run(
        args,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _run(
    tmp_path: Path, issue: str, targets: str, *, filler: int = 0, extra: tuple = ()
) -> set[int]:
    result = _execute(tmp_path, issue, targets, filler=filler, extra=extra)
    assert result.returncode == 0, f"the search failed:\n{result.stderr}"
    return {int(m) for m in re.findall(r"^#(\d+)\b", result.stdout, re.M)}


def _assert_fails_loudly(result: subprocess.CompletedProcess[str], what: str) -> None:
    assert result.returncode != 0, f"the search exited 0 although {what}"
    assert "SEARCH FAILED" in result.stdout + result.stderr, (
        "the search must say SEARCH FAILED so the stage does not record none found"
    )


def test_handoff_format_points_at_the_script() -> None:
    """The stages reach the search through this section, so it must name it."""
    text = HANDOFF_FORMAT.read_text()
    start = text.find(SECTION + "\n")
    assert start != -1, (
        f"{HANDOFF_FORMAT.relative_to(ROOT)} has no {SECTION!r} section, so neither "
        "entrance stage searches for a pull request on another branch"
    )
    rest = text[start + len(SECTION) :]
    end = re.search(r"^## ", rest, re.M)
    section = rest[: end.start()] if end else rest
    assert SCRIPT.relative_to(ROOT).as_posix() in section, (
        f"{SECTION!r} must tell the stages to run {SCRIPT.relative_to(ROOT)}"
    )


@pytest.mark.parametrize(
    ("issue", "targets", "expected"),
    [
        pytest.param(
            "25",
            "skills/infrahub-managing-checks/",
            {201, 204, 301, 305},
            id="issue-match-on-other-branches",
        ),
        # Part A runs at key derivation, before the stage knows any target.
        pytest.param(
            "25", "", {201, 204, 301, 305}, id="issue-match-before-targets-known"
        ),
        pytest.param(
            "",
            "skills/infrahub-managing-menus/",
            {203},
            id="file-overlap-without-issue",
        ),
        pytest.param(
            "25",
            "skills/infrahub-managing-menus/ scripts/check-symlinks.py",
            {201, 203, 204, 301, 305},
            id="issue-and-file-overlap",
        ),
        pytest.param("999", "skills/infrahub-managing-checks/", set(), id="no-match"),
    ],
)
def test_search_prints_exactly_the_matching_prs(
    tmp_path: Path, issue: str, targets: str, expected: set[int]
) -> None:
    """The search prints every matching PR and none of the near misses.

    Near misses that must not print: digits containing 25 (#202), #25 with
    a letter or underscore suffix (#208), a range ending at another number
    (#205), a path that only starts like the target (#206), a closed PR
    (#207), a merge already in HEAD (#302), and an unrelated merge (#303).
    #301 and #305 are both merged and not in HEAD: one has a merge commit
    this clone lacks, the other one it has fetched.
    """
    assert _run(tmp_path, issue, targets) == expected


def test_search_reads_past_the_first_page(tmp_path: Path) -> None:
    """A match older than the newest page of PRs is still found.

    150 open and 150 merged PRs that match nothing sit ahead of the real
    fixtures. A search that stops at a fixed `--limit` never reaches #201,
    #204, #301 or #305, and would record `none found` for a PR that exists.
    """
    assert _run(tmp_path, "25", "skills/infrahub-managing-checks/", filler=150) == {
        201,
        204,
        301,
        305,
    }


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
    ) == {201, 204, 301, 304, 305}


def test_search_reads_files_past_the_first_hundred(tmp_path: Path) -> None:
    """A target file listed after the 100th file of a PR is still matched.

    `gh pr list` returns at most 100 files per PR. #210 changes 120 files and
    the only one under the target is number 115, so a search that trusts the
    listed files never sees it.
    """
    files = tuple(f"docs/docs/page-{n}.mdx" for n in range(114))
    files += ("skills/infrahub-managing-transforms/rules/x.md",)
    files += tuple(f"docs/docs/late-{n}.mdx" for n in range(5))
    large = _pr(210, "OPEN", title="docs: large restructure", files=files)
    assert _run(
        tmp_path, "", "skills/infrahub-managing-transforms/", extra=(large,)
    ) == {210}


def test_search_fails_loudly_when_gh_fails(tmp_path: Path) -> None:
    """A failed `gh` call is an error, not an empty result.

    Printing nothing on failure reads exactly like "no matching PR", so the
    stage would record `none found` without having searched.
    """
    _assert_fails_loudly(_execute(tmp_path, "25", "", gh_fails=True), "gh failed")


def test_search_fails_loudly_on_data_it_cannot_read(tmp_path: Path) -> None:
    """A PR the search cannot parse is an error, not a skipped candidate.

    A PR whose `files` is null cannot be matched against the targets. Skipping
    it would record `none found` for a PR that was never checked.
    """
    broken = _pr(209, "OPEN")
    broken["files"] = None
    result = _execute(tmp_path, "", "skills/infrahub-managing-checks/", extra=(broken,))
    _assert_fails_loudly(result, "a PR could not be read")
