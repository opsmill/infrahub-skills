"""Tests for scripts/check-cli-invocations.py.

Bypasses the reviewer proved by mutating the real tree: a nested fence
inverts the tracked state, the ignore marker silences a whole line instead
of the one invocation it names, a second marker on the same line collides
with the first, and a marker written with the invocation's arguments does
not match the truncated form the scanner reports. All are reproduced here
against synthetic fixtures rather than by mutating real docs pages, so the
tests keep working however those pages are edited later.
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


def test_two_markers_on_one_line_do_not_collide(monkeypatch, tmp_path: Path) -> None:
    """The second-round reviewer's proof: a markdown bullet is one line, so
    a bullet naming two different invalid invocations needs two markers on
    that one line. `_IGNORE` used a greedy `.search`, so the first marker's
    capture swallowed the second marker whole, and neither invocation
    matched its own marker's (garbled) text, so both failed, including the
    first one, whose marker worked before a second marker was added.
    """
    lines = [
        "* Direct every write path: `infrahubctl generator run` and "  # cli-check: ignore infrahubctl generator run
        "`infrahubctl schema validate ./x`. "  # cli-check: ignore infrahubctl schema validate
        "<!-- cli-check: ignore infrahubctl generator run --> "
        "<!-- cli-check: ignore infrahubctl schema validate -->",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "two-markers.mdx", lines)
    assert "infrahubctl generator run" not in bad
    assert "infrahubctl schema validate" not in bad


def test_marker_naming_the_invocation_with_its_argument_matches(
    monkeypatch, tmp_path: Path
) -> None:
    """A marker names the command the way it actually reads in the prose,
    argument included, rather than the bare two-token form the scanner
    reports. The comment on `IGNORE_MARKER` promises the marker names "the
    exact invocation it silences"; comparing raw text made naming the
    command with its argument the one spelling that failed.
    """
    lines = [
        "Run `infrahubctl schema validate ./schemas`. "  # cli-check: ignore infrahubctl schema validate
        "<!-- cli-check: ignore infrahubctl schema validate ./schemas -->",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "with-argument.mdx", lines)
    assert bad == {}


# `gh search issues|prs --state` accepts only `open` or `closed`; `--state all`
# is rejected outright (#136). The shapes below are the ones the repo printed:
# two of the three split the command from its flag across a line break.
#
# This file is itself scanned, so no source line here may carry a backtick
# next to an invalid `--state` value. TICK and ALL keep them apart.
TICK = "`"
ALL = "all"


def _gh_findings(bad: dict) -> list[str]:
    return [shown for shown in bad if shown.startswith("gh ")]


def test_gh_search_without_state_passes(monkeypatch, tmp_path: Path) -> None:
    lines = [
        "```bash",
        'gh search issues --repo opsmill/infrahub-skills "output load order"',
        "```",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "compliant.md", lines)
    assert _gh_findings(bad) == []


def test_gh_search_with_valid_state_passes(monkeypatch, tmp_path: Path) -> None:
    """`--state open` is valid gh, wrong only by the analyzing-diagnostics
    search policy (`match-stable-search-keys.md`). The gate checks validity,
    not policy, so neither spelling of a valid value is flagged."""
    lines = [
        "```bash",
        'gh search issues --repo opsmill/infrahub --state open "Unable to find the schema"',
        'gh search prs --repo opsmill/infrahub --state=closed "schema"',
        "```",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "compliant-variant.md", lines)
    assert _gh_findings(bad) == []


def test_gh_search_state_all_on_one_line_is_flagged(monkeypatch, tmp_path: Path) -> None:
    """The `skills-reference/reporting-skill-gaps.mdx` shape."""
    lines = [
        "```bash",
        f'gh search issues --repo opsmill/infrahub-skills --state {ALL} "<skill name>"',
        "```",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "one-line.mdx", lines)
    assert [s for s in _gh_findings(bad) if "--state all" in s], bad


def test_gh_search_state_all_after_line_continuation_is_flagged(
    monkeypatch, tmp_path: Path
) -> None:
    """The `workflow-tracker-first.md` shape: the flag sits on the line after
    a `\\` continuation, so a per-line scan never sees it next to the
    command."""
    lines = [
        "```bash",
        "gh search issues --repo opsmill/infrahub-skills \\",
        f'  --state {ALL} "<skill name> <friction in plain terms>"',
        "```",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "continuation.md", lines)
    assert [s for s in _gh_findings(bad) if "--state all" in s], bad


def test_gh_search_state_all_in_wrapped_code_span_is_flagged(
    monkeypatch, tmp_path: Path
) -> None:
    """The `infrahub-reporting-issues/SKILL.md` step 4 shape: an inline code
    span opens on one line and closes on the next, so no single-line span
    holds both the command and the flag."""
    lines = [
        "1. **" + TICK + "gh" + TICK + "** CLI: " + TICK + "gh search issues --repo <owner/repo>",
        f'   --state {ALL} "<keywords>"' + TICK + ". Pull keywords from the",
        "   user's description plus any error message strings.",
    ]
    bad = _scan_only(monkeypatch, tmp_path, "wrapped-span.md", lines)
    assert [s for s in _gh_findings(bad) if "--state all" in s], bad


def test_real_repo_has_no_unignored_invalid_invocations() -> None:
    """The live check, as CI runs it."""
    bad = mod.scan()
    assert bad == {}, bad
