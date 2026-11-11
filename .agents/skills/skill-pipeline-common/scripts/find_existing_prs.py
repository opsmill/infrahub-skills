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
* changes a file under one of the `--target` path prefixes. A target may be
  relative to the current directory or absolute; it is matched as a path
  relative to the repository root, the form GitHub lists files in.

Closed, unmerged PRs are never printed. Each match is one line,
`#<number>\\t<state>\\t<branch>\\t<title>\\tmatched: <reason>`, where the
reason is `issue`, `files`, or `issue, files`.

The search is complete, not a sample:

* every open and every merged PR is read, doubling `--limit` until `gh`
  returns fewer than it was asked for;
* merged PRs are not narrowed by date, because a PR merged into a branch
  other than the default one can be old and still be missing from `HEAD`;
* `gh pr list` returns at most 100 files per PR, so a PR whose
  `changedFiles` is larger has its full file list read from the paginated
  pull-files endpoint before the target paths are matched.

It runs in the repository the stage works in and needs no fetch: a merge
commit missing from the local repository is not in `HEAD` either. That does
not hold in a shallow clone, where old commits of `HEAD` are missing too, so
the search refuses to run in one.

Exit codes
----------
  0  The search ran. Matches, if any, are on stdout; no output means none.
  1  The search did not complete (`gh` or `git` failed, returned data this
     script could not read, the checkout is shallow, or an argument was
     wrong: `--issue "#42"` instead of `--issue 42`, an empty `--target`,
     a target outside the repository, or neither option given).
     `SEARCH FAILED: <reason>` is on stderr.
     Never record this as "none found".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # noqa: S404
import sys
from typing import NoReturn

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


def match_reason(pr: dict, issue: int | None, targets: list[str]) -> str:
    """What matched, `issue`, `files` or both, or an empty string for no match."""
    reasons = []
    if issue is not None and names_issue(pr, issue):
        reasons.append("issue")
    if targets and touches(pr, targets):
        reasons.append("files")
    return ", ".join(reasons)


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _git(*args: str) -> int:
    return _run_git(*args).returncode


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
    shallow = _run_git("rev-parse", "--is-shallow-repository")
    if shallow.returncode != 0 or shallow.stdout.strip() != "false":
        # A missing merge commit would read as "not in HEAD" for every old PR.
        raise SearchFailed("the checkout is shallow; run git fetch --unshallow first")
    lines = []
    for pr in all_prs("open"):
        if reason := match_reason(pr, issue, targets):
            lines.append(
                f"#{pr['number']}\topen\t{pr['headRefName']}\t{pr['title']}"
                f"\tmatched: {reason}"
            )
    for pr in all_prs("merged"):
        reason = match_reason(pr, issue, targets)
        if reason and not in_head(pr["mergeCommit"]["oid"]):
            lines.append(
                f"#{pr['number']}\tmerged, not in HEAD\t{pr['headRefName']}"
                f"\t{pr['title']}\tmatched: {reason}"
            )
    return lines


def repo_relative(targets: list[str]) -> list[str]:
    """Each target as a path relative to the repository root, as GitHub lists files.

    `./skills/x/` and an absolute path name the same files as `skills/x/`, but
    would never match a PR file. An empty target, as an unset shell variable
    leaves, and a path outside the repository are errors, not dropped.
    """
    top = _run_git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise SearchFailed("not inside a git checkout")
    root = os.path.realpath(top.stdout.strip())
    cwd = os.path.realpath(os.getcwd())
    relative = []
    for target in targets:
        if not target.strip():
            raise SearchFailed("an empty --target was given, such as an unset variable")
        path = os.path.normpath(os.path.join(cwd, target))
        if os.path.commonpath([root, path]) != root:
            path = os.path.realpath(path)
        if os.path.commonpath([root, path]) != root:
            raise SearchFailed(f"--target {target} is outside the repository {root}")
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        if target.endswith(("/", os.sep)) and rel:
            rel += "/"
        relative.append(rel)
    return relative


class _Parser(argparse.ArgumentParser):
    """Report a wrong argument as SEARCH FAILED and exit 1, not argparse's 2."""

    def error(self, message: str) -> NoReturn:
        print(f"SEARCH FAILED: {message}. Nothing was searched.", file=sys.stderr)
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--issue", type=int, help="issue number the change is for, bare (42, not #42)"
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="path prefix the change touches; repeat for several",
    )
    args = parser.parse_args(argv)
    if args.issue is None and not args.target:
        parser.error("give --issue, --target, or both")
    try:
        lines = search(args.issue, repo_relative(args.target))
    except (SearchFailed, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SEARCH FAILED: {exc}. Nothing was searched.", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
