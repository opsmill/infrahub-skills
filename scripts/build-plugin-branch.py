#!/usr/bin/env python3
"""Commit the files the plugin ships to a branch of their own.

The Claude plugin directory validates every file in the plugin folder, and
this repository's plugin folder is its root. So the directory also read the
docs site, the evals, the graders and the tests: `eval.yaml` holds an
example GitHub token for a redaction eval, which blocked submission, and the
file count, the oversized files, `favicon.ico` and the routing symlinks each
raised a hold or a warning. None of them is part of the plugin.

This script builds a commit holding only `SHIPPED_PATHS`, plus each file in
`RENAMED_PATHS` at its branch path, taken from a source commit, and points
the plugin branch at it. The directory tracks that
branch instead of `main`, so its Branch or tag field must say `plugin`.

Each build is committed on top of the branch's previous build, so the branch
history is linear and every commit names the `main` commit it came from. A
build whose tree matches the previous one commits nothing.

The tree is assembled with git plumbing in a temporary index, so the working
tree and the real index are never touched.

Usage::

    python scripts/build-plugin-branch.py            # build and push
    python scripts/build-plugin-branch.py --no-push  # build, print the commit
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

# Everything a person who installs the plugin needs, and nothing else.
SHIPPED_PATHS = (
    ".claude-plugin",
    "skills",
    "LICENSE",
)

# Files shipped under another path: path in this repository -> path on the
# branch. The root README.md teaches `npx skills add` and `git clone` for the
# tools that are not Claude Code, and the directory holds a download-and-run
# command for review even in documentation. The plugin branch gets a README
# written for plugin users instead.
RENAMED_PATHS = {
    "plugin-branch/README.md": "README.md",
}


def _git(
    *args: str, env: dict[str, str] | None = None, stdin: str | None = None
) -> str:
    """Run git and return its stripped stdout, raising on a non-zero exit."""
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, env=env, input=stdin
    )
    return result.stdout.strip()


def _remote_head(remote: str, branch: str) -> str | None:
    """Return the commit the remote branch points at, or None if it does not exist."""
    output = _git("ls-remote", "--heads", remote, branch)
    if not output:
        return None
    sha = output.split()[0]
    _git("fetch", "--quiet", remote, sha)
    return sha


def _build_tree(source: str) -> str:
    """Write a tree holding SHIPPED_PATHS and RENAMED_PATHS from the source commit."""
    sources = (*SHIPPED_PATHS, *RENAMED_PATHS)
    missing = [path for path in sources if not _git("ls-tree", source, "--", path)]
    if missing:
        raise SystemExit(
            f"Source commit {source} lacks shipped paths: {', '.join(missing)}"
        )
    entries = [_git("ls-tree", "-r", "--full-tree", source, "--", *SHIPPED_PATHS)]
    for repo_path, branch_path in RENAMED_PATHS.items():
        # ls-tree prints "<mode> <type> <sha>\t<path>"; keep the blob, swap the path.
        blob = _git("ls-tree", "--full-tree", source, "--", repo_path).split("\t")[0]
        if blob.split()[1] != "blob":
            raise SystemExit(f"RENAMED_PATHS entry {repo_path} must be a file")
        entries.append(f"{blob}\t{branch_path}")
    listing = "\n".join(entries)
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(tmp, "index")}
        _git("update-index", "--index-info", env=env, stdin=listing + "\n")
        return _git("write-tree", env=env)


def main() -> int:
    """Build the plugin commit and, unless --no-push, push it to the branch."""
    parser = argparse.ArgumentParser(
        description="Commit the files the plugin ships to a branch."
    )
    parser.add_argument("--source", default="HEAD", help="commit to take files from")
    parser.add_argument("--branch", default="plugin", help="branch to publish to")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--no-push", action="store_true", help="build without pushing")
    args = parser.parse_args()

    source = _git("rev-parse", args.source)
    tree = _build_tree(source)
    parent = _remote_head(args.remote, args.branch)

    if parent is not None and _git("rev-parse", f"{parent}^{{tree}}") == tree:
        print(f"{args.branch} already matches {source[:12]}; nothing to commit.")
        return 0

    shipped = [*SHIPPED_PATHS, *(f"{a} as {b}" for a, b in RENAMED_PATHS.items())]
    message = f"Build plugin from {source}\n\nShipped paths: {', '.join(shipped)}"
    parent_args = ["-p", parent] if parent is not None else []
    commit = _git("commit-tree", tree, *parent_args, "-m", message)

    if args.no_push:
        print(commit)
        return 0
    _git("push", args.remote, f"{commit}:refs/heads/{args.branch}")
    print(f"Pushed {commit[:12]} to {args.branch} (built from {source[:12]}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
