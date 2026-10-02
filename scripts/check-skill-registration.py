#!/usr/bin/env python3
"""Check every user-invocable skill appears on every registration surface.

`dev/guidelines/skill-registration.md` lists the surfaces a new skill has to
appear on. The list alone did not hold: #159 wired the surfaces it named and
missed the router, and the Available Skills table in
`dev/guides/getting-started.md` fell seven skills behind across earlier
additions before it was replaced with a link. So the surfaces are checked.

Each surface is parsed rather than searched. A skill's name in AGENTS.md
prose, in a README install command, or in a router pair-table cell is not a
registration, so the check reads the table, tree, or array the entry has to
sit in.

What this does not check, because another script already does: that each
skill has a skills-reference page (`check-docs-skill-names.py`) and that
each page is in the sidebar (`check-docs-sidebar.py`).

Usage::

    python scripts/check-skill-registration.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The surface labels reported, one per place a skill has to appear.
AGENTS = "AGENTS.md"
README_TABLE = "README.md skills table"
README_TREE = "README.md project tree"
FRONT_PAGE = "docs/docs/readme.mdx"
ROUTER = "docs/docs/choosing-a-skill.mdx"
ROUTER_COUNT = "docs/docs/choosing-a-skill.mdx skill count"
MANIFEST = ".github/.release-manifest.json"
PAGE_SECTIONS = "reference page sections"

# The first `##` sections every skills-reference page carries, in this order.
# Pages add their own after them.
SECTIONS = [
    "When to use",
    "What it produces",
    "Example prompts",
    "Key rules enforced",
    "Common mistakes it catches",
]

# Carried by exactly the pages whose skill the router names in a pair-table
# heading: the section points the reader at that table.
NOT_SURE = "Not sure this is the right skill?"

# The router opens with the count spelled out ("Fifteen skills is ...").
_UNITS = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()

# Same frontmatter handling as check-docs-skill-names.py: the exemption is
# read from the skill's own frontmatter block, never from its body.
_FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
_USER_INVOCABLE_FALSE = re.compile(r"^user-invocable:\s*false\s*$", re.MULTILINE)

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_DELIMITER_ROW = re.compile(r"^\|[\s:|-]+\|$")
_PAGE_LINK = re.compile(r"\[([^\]]+)\]\(\./skills-reference/([a-z0-9-]+)\.mdx\)")
_TREE_ENTRY = re.compile(r"^[│\s]*[├└]──\s+([A-Za-z0-9._-]+)/")
# A fence opens with three or more backticks or tildes, and closes on a run of
# the same character at least as long.
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def spelled_number(word: str) -> int | None:
    """0 to 99 from its English spelling ("fifteen", "Twenty-six"), else None."""
    word = word.lower()
    if word in _UNITS:
        return _UNITS.index(word)
    tens, _, unit = word.partition("-")
    if tens not in _TENS:
        return None
    value = 20 + 10 * _TENS.index(tens)
    if not unit:
        return value
    if unit in _UNITS[1:10]:
        return value + _UNITS.index(unit)
    return None


def user_invocable_skills(skills_dir: Path) -> list[str]:
    """Skill directory names, minus those declaring `user-invocable: false`."""
    if not skills_dir.is_dir():
        return []
    names: list[str] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        match = _FRONTMATTER.match(skill_md.read_text(encoding="utf-8"))
        if match and _USER_INVOCABLE_FALSE.search(match.group(1)):
            continue
        names.append(skill_dir.name)
    return names


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub("", text, count=1)


def _split_fences(text: str) -> tuple[list[str], list[str]]:
    """(lines outside fenced code blocks, lines inside them)."""
    outside: list[str] = []
    inside: list[str] = []
    opener = ""
    for line in text.splitlines():
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if not opener:
                opener = marker
                continue
            if marker[0] == opener[0] and len(marker) >= len(opener):
                opener = ""
                continue
        (inside if opener else outside).append(line)
    return outside, inside


def _outside_fences(text: str) -> list[str]:
    return _split_fences(text)[0]


def _inside_fences(text: str) -> list[str]:
    return _split_fences(text)[1]


def _section(lines: list[str], level: int, title: str) -> list[str]:
    """The lines under the heading `title` at `level`, up to the next heading
    at that level or above."""
    body: list[str] = []
    inside = False
    for line in lines:
        match = _HEADING.match(line)
        if match and len(match.group(1)) <= level:
            if inside:
                break
            inside = len(match.group(1)) == level and match.group(2) == title
            continue
        if inside:
            body.append(line)
    return body


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _tables(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe table in `lines`, as (header cells, body rows)."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    i = 0
    while i < len(lines):
        is_header = lines[i].lstrip().startswith("|") and i + 1 < len(lines)
        if is_header and _DELIMITER_ROW.match(lines[i + 1].strip()):
            header = _cells(lines[i])
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            tables.append((header, rows))
        else:
            i += 1
    return tables


def _first_cells(lines: list[str]) -> list[str]:
    return [row[0] for _header, rows in _tables(lines) for row in rows if row]


def _agents_names(root: Path) -> set[str]:
    lines = _outside_fences(_read(root / "AGENTS.md"))
    skills = _section(_section(lines, 2, "Quick Reference"), 3, "Skills")
    return {cell.strip("`") for cell in _first_cells(skills)}


def _readme_table_names(root: Path) -> set[str]:
    lines = _outside_fences(_read(root / "README.md"))
    return {cell.strip("*") for cell in _first_cells(_section(lines, 2, "Skills"))}


def _readme_tree_names(root: Path) -> set[str]:
    # The tree is a fenced block, so read the section's fenced lines only.
    section = "\n".join(
        _section(_read(root / "README.md").splitlines(), 2, "Project Structure")
    )
    names: set[str] = set()
    for line in _inside_fences(section):
        match = _TREE_ENTRY.match(line)
        if match:
            names.add(match.group(1))
    return names


def _front_page_pages(root: Path) -> set[str]:
    lines = _outside_fences(_read(root / "docs" / "docs" / "readme.mdx"))
    pages: set[str] = set()
    for cell in _first_cells(_section(lines, 2, "Skills included")):
        match = _PAGE_LINK.search(cell)
        if match:
            pages.add(match.group(2))
    return pages


def _router(root: Path) -> tuple[set[str], set[str], int | None]:
    """(pages with a "Go to" row, pages named in a pair heading, stated count)."""
    text = _strip_frontmatter(_read(root / "docs" / "docs" / "choosing-a-skill.mdx"))
    lines = _outside_fences(text)

    routed: set[str] = set()
    display: dict[str, str] = {}
    for header, rows in _tables(_section(lines, 2, "Start from what you have")):
        if not header or header[-1] != "Go to":
            continue
        for row in rows:
            for label, page in _PAGE_LINK.findall(row[-1]):
                routed.add(page)
                display[label] = page

    paired: set[str] = set()
    for line in _section(lines, 2, "Pairs that are easy to confuse"):
        match = _HEADING.match(line)
        if match and len(match.group(1)) == 3:
            for part in match.group(2).split(","):
                if part.strip() in display:
                    paired.add(display[part.strip()])

    first = next((line for line in lines if line.strip()), "")
    count = spelled_number(first.split(" ", 1)[0])
    return routed, paired, count


def _manifest_names(root: Path) -> set[str]:
    try:
        data = json.loads(_read(root / ".github" / ".release-manifest.json"))
    except ValueError:
        return set()
    skills = data.get("skills", []) if isinstance(data, dict) else []
    return {name for name in skills if isinstance(name, str)}


def _page_ok(page: Path, paired: bool) -> bool:
    headings = [
        match.group(2)
        for line in _outside_fences(_strip_frontmatter(_read(page)))
        if (match := _HEADING.match(line)) and len(match.group(1)) == 2
    ]
    opens_right = headings[: len(SECTIONS)] == SECTIONS
    return opens_right and (NOT_SURE in headings) == paired


def check_registration(root: Path) -> list[tuple[str, str]]:
    """Return (skill, surface) for every surface a user-invocable skill is
    missing from. The router count is reported as ("", ROUTER_COUNT)."""
    skills = user_invocable_skills(root / "skills")
    agents = _agents_names(root)
    readme_table = _readme_table_names(root)
    readme_tree = _readme_tree_names(root)
    front_page = _front_page_pages(root)
    routed, paired, count = _router(root)
    manifest = _manifest_names(root)
    pages = root / "docs" / "docs" / "skills-reference"

    failures: list[tuple[str, str]] = []
    if count != len(skills):
        failures.append(("", ROUTER_COUNT))
    for name in skills:
        short = name.removeprefix("infrahub-")
        if name not in agents:
            failures.append((name, AGENTS))
        if short not in readme_table:
            failures.append((name, README_TABLE))
        if name not in readme_tree:
            failures.append((name, README_TREE))
        if short not in front_page:
            failures.append((name, FRONT_PAGE))
        if short not in routed:
            failures.append((name, ROUTER))
        if name not in manifest:
            failures.append((name, MANIFEST))
        page = pages / f"{short}.mdx"
        if page.is_file() and not _page_ok(page, short in paired):
            failures.append((name, PAGE_SECTIONS))
    return failures


def main() -> int:
    skills = user_invocable_skills(ROOT / "skills")
    if not skills:
        print(f"FAIL: no user-invocable skills found under {ROOT / 'skills'}.")
        return 1

    failures = check_registration(ROOT)
    if not failures:
        print(
            f"OK: all {len(skills)} user-invocable skills appear on every registration surface."
        )
        return 0

    print(f"FAIL: {len(failures)} registration gap(s).\n")
    for name, surface in failures:
        if surface == ROUTER_COUNT:
            print(f"  {surface}: the opening count does not spell out {len(skills)}")
        elif surface == PAGE_SECTIONS:
            print(
                f"  {name}: {surface} need to open with {', '.join(SECTIONS)} in order, and "
                f"'{NOT_SURE}' exactly when the router has a pair table naming it"
            )
        else:
            print(f"  {name}: missing from {surface}")
    print("\nThe surfaces and what each needs: dev/guidelines/skill-registration.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
