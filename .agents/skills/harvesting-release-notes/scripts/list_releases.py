#!/usr/bin/env python3
"""Expand a release spec into the release tags to read, in version order.

    list_releases.py "<spec>" [--releases-json PATH | --notes-dir DIR] [--include-prereleases]

A spec is one release or an inclusive `from..to` range, with an optional
repository word in front:

    1.12.1                              opsmill/infrahub
    1.11.0..1.12.1                      opsmill/infrahub
    infrahub-v1.11.0..infrahub-v1.12.1  opsmill/infrahub
    sdk 1.23.0..1.24.0                  opsmill/infrahub-sdk-python
    mcp 1.2.0..1.3.0                    opsmill/infrahub-mcp-server

Prints `<owner/repo> <tag>` per line, sorted by version. Publish dates are
ignored: a patch to an older minor is often published after the next minor's
pre-release. Pre-releases are left out unless `--include-prereleases` is given
or the spec names one as an end of the range.

The release list comes from `gh release list` unless `--releases-json` names a
file holding that command's JSON output, or `--notes-dir` names a directory of
`<tag>.md` release notes. Exits non-zero, naming the spec, when an end of the
range is not a known release.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPOS = {
    "infrahub": "opsmill/infrahub",
    "sdk": "opsmill/infrahub-sdk-python",
    "mcp": "opsmill/infrahub-mcp-server",
}

_TAG_RE = re.compile(r"^(?P<prefix>infrahub-)?v?(?P<ver>\d+\.\d+\.\d+)(?:(?P<kind>a|b|rc)(?P<n>\d+))?$")
_PRE_ORDER = {"a": 0, "b": 1, "rc": 2}


def version_key(tag: str) -> tuple[int, int, int, int, int, int] | None:
    """A sort key for a tag, or None when the tag is not a version.

    A pre-release sorts before the final release of the same version.
    """
    m = _TAG_RE.match(tag)
    if not m:
        return None
    major, minor, patch = (int(p) for p in m.group("ver").split("."))
    if m.group("kind"):
        return major, minor, patch, 0, _PRE_ORDER[m.group("kind")], int(m.group("n"))
    return major, minor, patch, 1, 0, 0


def parse_spec(spec: str) -> tuple[str, str, str]:
    """(repository, from, to) for a spec. Raises ValueError when it does not parse."""
    words = spec.split()
    if len(words) == 2 and words[0].lower() in REPOS:
        repo_word, span = words[0].lower(), words[1]
    elif len(words) == 1:
        repo_word, span = None, words[0]
    else:
        raise ValueError(f"cannot parse release spec {spec!r}")
    start, _, end = span.partition("..")
    end = end or start
    for end_point in (start, end):
        if version_key(end_point) is None:
            raise ValueError(f"{end_point!r} in {spec!r} is not a release version")
    names_infrahub = start.startswith("infrahub-") or end.startswith("infrahub-")
    if repo_word is None:
        repo_word = "infrahub"
    elif names_infrahub and repo_word != "infrahub":
        raise ValueError(f"{spec!r} names an infrahub- tag with the {repo_word!r} repository")
    return REPOS[repo_word], start, end


def load_releases(repo: str, releases_json: Path | None, notes_dir: Path | None) -> list[dict]:
    if releases_json is not None:
        return json.loads(releases_json.read_text())
    if notes_dir is not None:
        # A pre-release is recognised from the tag itself (`1.7.0b1`).
        return [
            {"tagName": p.stem, "isPrerelease": version_key(p.stem)[3] == 0}
            for p in sorted(notes_dir.glob("*.md"))
            if version_key(p.stem) is not None
        ]
    out = subprocess.run(
        ["gh", "release", "list", "-R", repo, "--limit", "1000", "--json", "tagName,isPrerelease,publishedAt"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"gh release list -R {repo} failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def expand(spec: str, releases: list[dict], include_prereleases: bool) -> list[str]:
    repo, start, end = parse_spec(spec)
    by_version = {version_key(r["tagName"]): r for r in releases if version_key(r["tagName"]) is not None}
    lo, hi = version_key(start), version_key(end)
    for end_point, key in ((start, lo), (end, hi)):
        if key not in by_version:
            raise LookupError(f"{end_point} is not a release of {repo} (spec {spec!r})")
    tags = []
    for key in sorted(by_version):
        if not lo <= key <= hi:
            continue
        rel = by_version[key]
        prerelease = rel.get("isPrerelease") or key[3] == 0
        if prerelease and not include_prereleases and key not in (lo, hi):
            continue
        tags.append(rel["tagName"])
    return [f"{repo} {tag}" for tag in tags]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("spec", help='a release or range, for example "1.11.0..1.12.1" or "sdk 1.24.0"')
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--releases-json", type=Path, help="gh release list --json output, instead of calling gh")
    source.add_argument("--notes-dir", type=Path, help="a directory of <tag>.md release notes, instead of calling gh")
    parser.add_argument("--include-prereleases", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo, _, _ = parse_spec(args.spec)
        releases = load_releases(repo, args.releases_json, args.notes_dir)
        for line in expand(args.spec, releases, args.include_prereleases):
            print(line)
    except (ValueError, LookupError, RuntimeError) as exc:
        print(f"list_releases: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
