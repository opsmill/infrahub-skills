"""Tests for graders/teaching-concepts/lib.py.

Each check gets one compliant fixture and near-miss violating fixtures.
A grader that passes a violating fixture is a silently broken assertion.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LIB_PATH = REPO_ROOT / "graders" / "teaching-concepts" / "lib.py"

spec = importlib.util.spec_from_file_location("teaching_lib", LIB_PATH)
teaching_lib = importlib.util.module_from_spec(spec)
sys.modules["teaching_lib"] = teaching_lib
spec.loader.exec_module(teaching_lib)


def make_ws(tmp_path, lesson=None, solution=None, progress=None,
            reply=None, concept="schema"):
    """Build a .infrahub-learning workspace under tmp_path."""
    root = tmp_path / ".infrahub-learning"
    if lesson is not None:
        (root / "lessons").mkdir(parents=True, exist_ok=True)
        (root / "lessons" / f"{concept}.md").write_text(lesson)
    if solution is not None:
        (root / "solutions").mkdir(parents=True, exist_ok=True)
        (root / "solutions" / f"{concept}.md").write_text(solution)
    if progress is not None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "progress.md").write_text(progress)
    if reply is not None:
        (tmp_path / "reply.md").write_text(reply)
    return tmp_path


def test_sections_splits_on_h2():
    text = "# Title\n## Probe\nq1?\nq2?\n## Explain\nbody\n"
    parts = teaching_lib.sections(text)
    assert list(parts) == ["Probe", "Explain"]
    assert "q1?" in parts["Probe"]
    assert "body" in parts["Explain"]


def test_headings_order():
    text = "## Probe\nx\n## Explain\ny\n## Exercise\nz\n## Check\nw\n"
    assert teaching_lib.headings(text) == ["Probe", "Explain", "Exercise", "Check"]


def test_code_blocks_extracts_fences():
    text = "pre\n```yaml\nkind: X\n```\npost\n```\nplain\n```\n"
    assert teaching_lib.code_blocks(text) == ["kind: X", "plain"]


def test_lessons_lists_workspace(tmp_path):
    ws = make_ws(tmp_path, lesson="## Probe\n", concept="objects")
    found = teaching_lib.lessons(ws)
    assert [p.name for p in found] == ["objects.md"]


def test_lessons_empty_when_no_workspace(tmp_path):
    assert teaching_lib.lessons(tmp_path) == []


def test_run_checks_scores_and_reports(tmp_path, monkeypatch):
    monkeypatch.setitem(teaching_lib.CHECKS, "always-pass",
                        lambda ws: (True, "ok"))
    monkeypatch.setitem(teaching_lib.CHECKS, "always-fail",
                        lambda ws: (False, "bad"))
    result = teaching_lib.run_checks(["always-pass", "always-fail"], tmp_path)
    assert result["score"] == 0.5
    assert result["checks"][0]["passed"] is True
    assert "bad" in result["details"]


def test_run_checks_survives_crashing_check(tmp_path, monkeypatch):
    def boom(ws):
        raise ValueError("kaput")
    monkeypatch.setitem(teaching_lib.CHECKS, "crasher", boom)
    result = teaching_lib.run_checks(["crasher"], tmp_path)
    assert result["score"] == 0.0
    assert "crash" in result["checks"][0]["message"]
