#!/usr/bin/env python3
"""Find pull requests that already cover a skill change, before it is built.

The skill-change pipeline's own PR lookups (`gh pr list --head "$BRANCH"`)
only see the pipeline's branch. This script searches every branch, so an
entrance stage can stop before analysing or designing a change somebody
already made.

Usage
-----
    python find_existing_prs.py [--issue N] [--target PATH ...]

A PR is printed when it is open, or merged with a merge commit that is not an
ancestor of `HEAD`, and it does at least one of:

* lists issue N of this repository among the issues it closes (a PR that
  closes issue N of another repository does not count);
* names `#N` as a whole token in its title or body (`#25`, not `#250`,
  `#25abc` or `#25_old`);
* changes a file under one of the `--target` path prefixes.

Closed, unmerged PRs are never printed. Each match is one line,
`#<number>\\t<state>\\t<branch>\\t<title>`.

The search is complete, not a sample:

* every open and every merged PR is read, doubling `--limit` until `gh`
  returns fewer than it was asked for;
* merged PRs are not narrowed by date, because a PR merged into a branch
  other than the default one can be old and still be missing from `HEAD`;
* `gh pr list` returns at most 100 files per PR, so a PR whose
  `changedFiles` is larger has its full file list read from the paginated
  pull-files endpoint before the target paths are matched.

It runs in the repository the stage works in and needs no fetch: a merge
commit missing from the local repository is not in `HEAD` either.

Exit codes
----------
  0  The search ran. Matches, if any, are on stdout; no output means none.
  1  The search did not complete (`gh` or `git` failed, or returned data
     this script could not read). `SEARCH FAILED: <reason>` is on stderr.
     Never record this as "none found".
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # noqa: S404
import sys

FIELDS = "number,title,body,headRefName,closingIssuesReferences,files,changedFiles,mergeCommit"
FIRST_PAGE = 100


class SearchFailed(Exception):
    """The search could not complete, so its empty result means nothing."""


def _gh(*args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["gh", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SearchFailed(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout


def all_prs(state: str) -> list[dict]:
    """Every PR in `state`, doubling --limit until the list stops short."""
    limit = FIRST_PAGE
    while True:
        out = _gh(
            "pr", "list", "--state", state, "--limit", str(limit), "--json", FIELDS
        )
        prs = json.loads(out)
        if len(prs) < limit:
            return prs
        limit *= 2


def all_files(pr: dict) -> list[str]:
    """The PR's changed paths, read in full when gh pr list cut them off."""
    paths = [f["path"] for f in pr["files"]]
    if pr.get("changedFiles", 0) <= len(paths):
        return paths
    out = _gh(
        "api",
        "--paginate",
        f"repos/{{owner}}/{{repo}}/pulls/{pr['number']}/files",
        "--jq",
        ".[].filename",
    )
    return out.splitlines()


_REPO: list[str] = []


def this_repo() -> str:
    """`owner/name` of the repository gh works in, looked up once."""
    if not _REPO:
        out = _gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
        _REPO.append(out.strip().lower())
    return _REPO[0]


def closes_here(ref: dict, issue: int) -> bool:
    """Whether a closing reference is issue N in this repository, not N elsewhere."""
    if ref["number"] != issue:
        return False
    repo = ref.get("repository")
    if not repo:
        return True
    return f"{repo['owner']['login']}/{repo['name']}".lower() == this_repo()


def names_issue(pr: dict, issue: int) -> bool:
    if any(closes_here(ref, issue) for ref in pr["closingIssuesReferences"]):
        return True
    text = f"{pr.get('title') or ''} {pr.get('body') or ''}"
    return re.search(rf"(^|[^0-9A-Za-z])#{issue}([^0-9A-Za-z_]|$)", text) is not None


def touches(pr: dict, targets: list[str]) -> bool:
    return any(path.startswith(t) for path in all_files(pr) for t in targets)


def matches(pr: dict, issue: int | None, targets: list[str]) -> bool:
    if issue is not None and names_issue(pr, issue):
        return True
    return bool(targets) and touches(pr, targets)


def _git(*args: str) -> int:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        check=False,
    ).returncode


def in_head(sha: str) -> bool:
    """Whether HEAD contains the commit, judged by exit codes, not git's wording."""
    if _git("cat-file", "-e", f"{sha}^{{commit}}") != 0:
        return False  # a commit this clone does not have cannot be in HEAD
    code = _git("merge-base", "--is-ancestor", sha, "HEAD")
    if code not in (0, 1):
        raise SearchFailed(f"git merge-base --is-ancestor {sha} HEAD exited {code}")
    return code == 0


def search(issue: int | None, targets: list[str]) -> list[str]:
    if _git("rev-parse", "--verify", "--quiet", "HEAD") != 0:
        raise SearchFailed("not inside a git checkout with a HEAD commit")
    lines = []
    for pr in all_prs("open"):
        if matches(pr, issue, targets):
            lines.append(f"#{pr['number']}\topen\t{pr['headRefName']}\t{pr['title']}")
    for pr in all_prs("merged"):
        if matches(pr, issue, targets) and not in_head(pr["mergeCommit"]["oid"]):
            lines.append(
                f"#{pr['number']}\tmerged, not in HEAD\t{pr['headRefName']}\t{pr['title']}"
            )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--issue", type=int, help="issue number the change is for")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="path prefix the change touches; repeat for several",
    )
    args = parser.parse_args(argv)
    targets = [t for t in args.target if t]
    try:
        lines = search(args.issue, targets)
    except (SearchFailed, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SEARCH FAILED: {exc}. Nothing was searched.", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
