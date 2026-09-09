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


COMPLIANT_LESSON = """# Lesson: schema relationships

## Probe
1. What does a relationship in Infrahub connect?
2. Have you used foreign keys in a database before?

## Explain
A relationship connects two schema nodes. Your `TestbedSensor` node points
to `TestbedZone`. Cardinality controls how many peers one object can have.
See https://docs.infrahub.app/topics/schema for the full model.

## Exercise
**Your task:** Add a new relationship from `TestbedSensor` to a
`TestbedRack` node in your schema file and pick the right cardinality.

## Check
1. What happens if you omit cardinality?
2. Which side of the relationship owns the data?

Next step when you are ready: the infrahub-managing-schemas skill does
this work on real projects.
"""

COMPLIANT_SOLUTION = """# Solution: schema relationships

## Solution
```yaml
relationships:
  - name: rack
    peer: TestbedRack
    cardinality: one
    kind: Attribute
```

## Verification
Ran `python scripts/validate_schema.py sandbox/schema.yml` (in-memory
Infrahub validator): schema loads cleanly, relationship resolves.
"""

COMPLIANT_PROGRESS = """| concept | status | last-seen | notes |
|---|---|---|---|
| schema | introduced | 2026-09-09 | solution revealed on exercise |
| foundations | practiced | 2026-09-08 | |
"""


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


def test_structured_lessons_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["structured-lessons"](ws)
    assert ok, msg


def test_structured_lessons_missing_section(tmp_path):
    broken = COMPLIANT_LESSON.replace("## Check", "## Recap")
    ws = make_ws(tmp_path, lesson=broken)
    ok, msg = teaching_lib.CHECKS["structured-lessons"](ws)
    assert not ok and "Check" in msg


def test_structured_lessons_wrong_order(tmp_path):
    reordered = (
        "## Explain\nbody https://docs.infrahub.app/topics/schema\n"
        "## Probe\n1. q?\n2. q?\n## Exercise\n**Your task:** do it.\n"
        "## Check\nq?\n"
    )
    ws = make_ws(tmp_path, lesson=reordered)
    ok, msg = teaching_lib.CHECKS["structured-lessons"](ws)
    assert not ok and "order" in msg


def test_structured_lessons_no_lesson(tmp_path):
    ok, msg = teaching_lib.CHECKS["structured-lessons"](tmp_path)
    assert not ok


def test_probe_first_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["probe-first"](ws)
    assert ok, msg


def test_probe_first_too_few_questions(tmp_path):
    one_q = COMPLIANT_LESSON.replace(
        "2. Have you used foreign keys in a database before?", "")
    ws = make_ws(tmp_path, lesson=one_q)
    ok, msg = teaching_lib.CHECKS["probe-first"](ws)
    assert not ok and "question" in msg


def test_probe_first_too_many_questions(tmp_path):
    four_q = COMPLIANT_LESSON.replace(
        "## Explain",
        "3. Another question?\n4. Yet another?\n\n## Explain")
    ws = make_ws(tmp_path, lesson=four_q)
    ok, msg = teaching_lib.CHECKS["probe-first"](ws)
    assert not ok


def test_probe_first_probe_after_explain(tmp_path):
    swapped = (
        "## Explain\nbody\n## Probe\n1. q?\n2. q?\n"
        "## Exercise\n**Your task:** x\n## Check\nq?\n"
    )
    ws = make_ws(tmp_path, lesson=swapped)
    ok, msg = teaching_lib.CHECKS["probe-first"](ws)
    assert not ok


def test_cite_docs_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["cite-docs"](ws)
    assert ok, msg


def test_cite_docs_missing_link(tmp_path):
    no_link = COMPLIANT_LESSON.replace(
        "See https://docs.infrahub.app/topics/schema for the full model.", "")
    ws = make_ws(tmp_path, lesson=no_link)
    ok, msg = teaching_lib.CHECKS["cite-docs"](ws)
    assert not ok


def test_cite_docs_link_outside_explain_does_not_count(tmp_path):
    moved = no_link = COMPLIANT_LESSON.replace(
        "See https://docs.infrahub.app/topics/schema for the full model.", "")
    moved = moved.replace(
        "## Check", "## Check\nhttps://docs.infrahub.app/topics/schema\n")
    ws = make_ws(tmp_path, lesson=moved)
    ok, msg = teaching_lib.CHECKS["cite-docs"](ws)
    assert not ok


def test_record_progress_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 progress=COMPLIANT_PROGRESS)
    ok, msg = teaching_lib.CHECKS["record-progress"](ws)
    assert ok, msg


def test_record_progress_missing_file(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["record-progress"](ws)
    assert not ok


def test_record_progress_wrong_header(tmp_path):
    bad = COMPLIANT_PROGRESS.replace("last-seen", "date")
    ws = make_ws(tmp_path, progress=bad)
    ok, msg = teaching_lib.CHECKS["record-progress"](ws)
    assert not ok and "header" in msg


def test_record_progress_invalid_status(tmp_path):
    bad = COMPLIANT_PROGRESS.replace("introduced", "mastered")
    ws = make_ws(tmp_path, progress=bad)
    ok, msg = teaching_lib.CHECKS["record-progress"](ws)
    assert not ok and "mastered" in msg


def test_record_progress_no_rows(tmp_path):
    header_only = "| concept | status | last-seen | notes |\n|---|---|---|---|\n"
    ws = make_ws(tmp_path, progress=header_only)
    ok, msg = teaching_lib.CHECKS["record-progress"](ws)
    assert not ok


def test_verified_solution_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 solution=COMPLIANT_SOLUTION)
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert ok, msg


def test_verified_solution_missing_file(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert not ok and "solution" in msg


def test_verified_solution_no_verification_section(tmp_path):
    unverified = COMPLIANT_SOLUTION.split("## Verification")[0]
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=unverified)
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert not ok and "Verification" in msg


def test_verified_solution_empty_solution_section(tmp_path):
    empty = "## Solution\n\n## Verification\nran the validator, clean.\n"
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=empty)
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert not ok


def test_learner_authors_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 solution=COMPLIANT_SOLUTION)
    ok, msg = teaching_lib.CHECKS["learner-authors"](ws)
    assert ok, msg


def test_learner_authors_missing_task_marker(tmp_path):
    no_marker = COMPLIANT_LESSON.replace("**Your task:**", "Try this:")
    ws = make_ws(tmp_path, lesson=no_marker, solution=COMPLIANT_SOLUTION)
    ok, msg = teaching_lib.CHECKS["learner-authors"](ws)
    assert not ok and "Your task" in msg


def test_learner_authors_solution_leaked_into_lesson(tmp_path):
    leaked = COMPLIANT_LESSON.replace(
        "## Check",
        "```yaml\nrelationships:\n  - name: rack\n    peer: TestbedRack\n"
        "    cardinality: one\n    kind: Attribute\n```\n\n## Check",
    )
    ws = make_ws(tmp_path, lesson=leaked, solution=COMPLIANT_SOLUTION)
    ok, msg = teaching_lib.CHECKS["learner-authors"](ws)
    assert not ok and "solution" in msg.lower()


def test_hint_before_solution_pass(tmp_path):
    hint = ("Look again at the `peer` field. Which node kind should the "
            "sensor point at? Check your zone definition first.")
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 solution=COMPLIANT_SOLUTION, reply=hint)
    ok, msg = teaching_lib.CHECKS["hint-before-solution"](ws)
    assert ok, msg


def test_hint_before_solution_missing_reply(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["hint-before-solution"](ws)
    assert not ok


def test_hint_before_solution_reply_is_the_solution(tmp_path):
    spoiler = ("Here you go:\n```yaml\nrelationships:\n  - name: rack\n"
               "    peer: TestbedRack\n    cardinality: one\n"
               "    kind: Attribute\n```\n")
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 solution=COMPLIANT_SOLUTION, reply=spoiler)
    ok, msg = teaching_lib.CHECKS["hint-before-solution"](ws)
    assert not ok


def test_hint_before_solution_rejects_any_long_code_block(tmp_path):
    other_code = ("Try:\n```yaml\nnodes:\n  - name: Foo\n    namespace: Bar\n"
                  "    label: Foo\n```\n")
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 solution=COMPLIANT_SOLUTION, reply=other_code)
    ok, msg = teaching_lib.CHECKS["hint-before-solution"](ws)
    assert not ok


def test_status_stays_introduced_pass(tmp_path):
    ws = make_ws(tmp_path, progress=COMPLIANT_PROGRESS)
    ok, msg = teaching_lib.CHECKS["status-stays-introduced"](ws)
    assert ok, msg


def test_status_stays_introduced_promoted_anyway(tmp_path):
    promoted = COMPLIANT_PROGRESS.replace(
        "| schema | introduced |", "| schema | practiced |")
    ws = make_ws(tmp_path, progress=promoted)
    ok, msg = teaching_lib.CHECKS["status-stays-introduced"](ws)
    assert not ok


def test_status_stays_introduced_concept_missing(tmp_path):
    only_other = "| concept | status | last-seen | notes |\n|---|---|---|---|\n| menus | practiced | 2026-09-09 | |\n"
    ws = make_ws(tmp_path, progress=only_other)
    ok, msg = teaching_lib.CHECKS["status-stays-introduced"](ws)
    assert not ok
