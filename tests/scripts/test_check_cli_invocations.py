"""Tests for scripts/check-cli-invocations.py.

Two bypasses the reviewer proved by mutating the real tree: a nested fence
inverts the tracked state, and the ignore marker silences a whole line
instead of the one invocation it names. Both are reproduced here against
synthetic fixtures rather than by mutating real docs pages, so the tests
keep working however those pages are edited later.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = ROOT / "scripts" / "check-cli-invocations.py"
_spec = importlib.util.spec_from_file_location("check_cli_invocations", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _scan_only(monkeypatch, tmp_path: Path, filename: str, lines: list[str]):
    """Run scan() against a single synthetic file instead of the real tree."""
    path = tmp_path / filename
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_files", lambda: [path])
    return mod.scan()


def test_nested_fence_does_not_invert_the_tracked_state(monkeypatch, tmp_path: Path) -> None:
    """The reviewer's proof: a bad command inside a ```yaml block nested
    inside a four-backtick markdown block, matching the structure
    `docs/docs/contributing/anatomy-of-a-skill.mdx` uses to show a rule's
    own fenced examples.

    A fence only closes on a run of backticks at least as long as the one
    that opened it (the CommonMark rule). Toggling on any run of three or
    more flips the state on the inner fence's marker line, and everything
    after that reads as prose instead of shell input.
    """
    lines = [
        "````markdown",
        "---",
        "title: Example rule",
        "---",
        "",
        "### Incorrect",
        "",
        "```yaml",
        "infrahubctl schema validate ./x",
        "```",
        "",
        "### Correct",
        "",
        "```yaml",
        "infrahubctl schema check ./x",
        "```",
        "````",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "anatomy-of-a-skill.mdx", lines)
    assert "infrahubctl schema validate" in bad
    assert "infrahubctl schema check" not in bad


def test_ignore_marker_only_silences_the_named_invocation(monkeypatch, tmp_path: Path) -> None:
    """The reviewer's proof: appending a new, different bad invocation to a
    bullet already carrying an ignore marker for another one must not ride
    along on that marker — `IGNORE_MARKER in line` silenced the whole line
    regardless of what else was on it, which is how
    `release-1_2_6.mdx:36` could grow a second defect unnoticed.
    """
    lines = [
        "* Direct every write path — `infrahubctl object load`, and also "
        "`infrahubctl generator run`, and now also "  # cli-check: ignore infrahubctl generator run
        "`infrahubctl schema validate ./x`. "  # cli-check: ignore infrahubctl schema validate
        "<!-- cli-check: ignore infrahubctl generator run -->",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "release-1_2_6.mdx", lines)
    assert "infrahubctl generator run" not in bad
    assert "infrahubctl schema validate" in bad


def test_bare_ignore_marker_with_no_invocation_silences_nothing(
    monkeypatch, tmp_path: Path
) -> None:
    """A marker with nothing after it protects nothing, rather than
    protecting the whole line — the naming is what scopes it."""
    lines = [
        "Run `infrahubctl schema validate ./x`. "  # cli-check: ignore infrahubctl schema validate
        "<!-- cli-check: ignore -->",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "bare-marker.mdx", lines)
    assert "infrahubctl schema validate" in bad


def test_named_ignore_marker_still_silences_a_simple_line(monkeypatch, tmp_path: Path) -> None:
    """The common case must keep working: one bad invocation, one marker
    naming it, on an otherwise unremarkable line."""
    lines = [
        "Run `infrahubctl schema validate ./x`. "  # cli-check: ignore infrahubctl schema validate
        "<!-- cli-check: ignore infrahubctl schema validate -->",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "named-marker.mdx", lines)
    assert bad == {}


def test_real_repo_has_no_unignored_invalid_invocations() -> None:
    """The live check, as CI runs it."""
    bad = mod.scan()
    assert bad == {}, bad
