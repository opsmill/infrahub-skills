"""Assert every bash snippet printed by a contributor skill actually parses.

These snippets are instructions an agent runs verbatim, so a syntax error in
one is a broken instruction rather than a cosmetic defect. Two shipped here
before this test existed:

- `BRANCH=<the Branch field from ...>` on its own line. In sh an unquoted `<`
  opens a redirect, so the block died there and the `git checkout "$BRANCH"`
  below it ran against an empty variable.
- A close-out block that piped a single-quoted heredoc into `gh pr edit --body`,
  replacing a pull request description with the literal placeholder text.

`<placeholder>` spans are the documented way these snippets mark a fill-in, so
they are substituted before parsing rather than treated as an error. What is
checked is the shape of the shell around them.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "contributor-skills"

BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.S)
PLACEHOLDER = re.compile(r"<[^>\n]+>")


def _blocks() -> list[tuple[str, int, str]]:
    found = []
    for path in sorted(SKILL_DIR.glob("*/*.md")):
        rel = path.relative_to(ROOT).as_posix()
        for index, block in enumerate(BASH_BLOCK.findall(path.read_text())):
            found.append((rel, index, block))
    return found


BLOCKS = _blocks()


def test_snippets_were_found() -> None:
    """Guard against the glob silently matching nothing and the suite passing."""
    assert len(BLOCKS) > 10, f"only {len(BLOCKS)} bash blocks found; the glob is probably wrong"


@pytest.mark.parametrize(
    ("rel", "index", "block"), BLOCKS, ids=[f"{r}#{i}" for r, i, _ in BLOCKS]
)
def test_bash_block_parses(rel: str, index: int, block: str, tmp_path: Path) -> None:
    """`bash -n` accepts the block once its `<placeholder>` spans are filled."""
    script = tmp_path / "snippet.sh"
    script.write_text(PLACEHOLDER.sub("PLACEHOLDER", block))
    result = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"{rel} block {index} is not valid sh:\n{result.stderr}"


@pytest.mark.parametrize(
    ("rel", "index", "block"), BLOCKS, ids=[f"{r}#{i}" for r, i, _ in BLOCKS]
)
def test_no_bare_placeholder_assignment(rel: str, index: int, block: str) -> None:
    """A `VAR=<fill this in>` assignment is quoted, so `<` cannot open a redirect."""
    for line in block.splitlines():
        stripped = line.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=<", stripped):
            pytest.fail(
                f"{rel} block {index}: unquoted placeholder assignment {stripped!r}. "
                'Quote it as VAR="<...>" or sh reads the < as a redirect.'
            )
