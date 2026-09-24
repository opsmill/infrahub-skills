#!/usr/bin/env python3
"""Render a curated release-notes page as a GitHub Release body.

Reads ``docs/docs/release-notes/release-X_Y_Z.mdx`` and prints GitHub-flavored
Markdown: everything from the first ``## `` heading on (the frontmatter and the
metadata table are site-only), Docusaurus admonitions turned into blockquotes,
and relative links into the docs site reduced to their text, since they do not
resolve on GitHub. With ``--previous-tag``, a Full Changelog compare link is
appended. release.yml appends the skills list after publishing.

Usage: release_body.py VERSION [--previous-tag vX.Y.Z]
"""

import argparse
import re
import sys
from pathlib import Path

REPO = "opsmill/infrahub-skills"
NOTES_DIR = Path(__file__).resolve().parent.parent / "docs" / "docs" / "release-notes"

ADMONITION = re.compile(r"^:::(\w+)[ \t]*([^\n]*)\n(.*?)\n:::[ \t]*$", re.S | re.M)
RELATIVE_LINK = re.compile(r"\[([^\]]+)\]\((?!https?:|#|mailto:)[^)]+\)")


def notes_path(version: str) -> Path:
    return NOTES_DIR / f"release-{version.replace('.', '_')}.mdx"


def _blockquote(match: re.Match) -> str:
    kind, title, inner = match.groups()
    lines = [f"> **{title.strip() or kind.capitalize()}**", ">"]
    lines += [
        f"> {line}" if line.strip() else ">" for line in inner.strip("\n").split("\n")
    ]
    return "\n".join(lines)


def render(mdx: str, version: str, previous_tag: str | None = None) -> str:
    start = re.search(r"^## ", mdx, re.M)
    if start is None:
        raise ValueError(
            "release-notes page has no '## ' heading to start the body from"
        )
    body = mdx[start.start() :]
    body = ADMONITION.sub(_blockquote, body)
    body = RELATIVE_LINK.sub(r"\1", body)
    body = body.rstrip() + "\n"
    if previous_tag:
        compare = f"https://github.com/{REPO}/compare/{previous_tag}...v{version}"
        body += f"\n---\n\n**Full Changelog**: {compare}\n"
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "version", help="release version without the leading v, e.g. 1.3.0"
    )
    parser.add_argument("--previous-tag", help="tag to compare against, e.g. v1.2.8")
    args = parser.parse_args()

    path = notes_path(args.version)
    if not path.is_file():
        print(f"no release-notes page at {path}", file=sys.stderr)
        return 1
    sys.stdout.write(render(path.read_text(), args.version, args.previous_tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
