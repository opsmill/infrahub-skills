"""Tests for graders/teaching-concepts/lib.py.

Each check gets the four fixtures dev/guides/adding-a-rule.md requires:
compliant, compliant phrased differently, violating, and a violating
near-miss that satisfies the check's keyword. The two variants are the
ones that find bugs — a false fail on re-worded but correct output, and
laundering by a violation that mentions the right word.
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
    moved = COMPLIANT_LESSON.replace(
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


def test_verified_solution_vacuous_assurance_rejected(tmp_path):
    vacuous = COMPLIANT_SOLUTION.split("## Verification")[0] + (
        "## Verification\nThis should work.\n"
    )
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=vacuous)
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


SANDBOX_LESSON = """# Lesson: proposed changes

## Probe
1. Have you merged a git branch before?
2. What do you expect a review to catch?

## Explain
A proposed change is Infrahub's review pipeline.
See https://docs.infrahub.app/topics/proposed-change for details.

## Exercise
This exercise writes to your instance. Shall we create a scratch branch for it?

**Your task:** After you confirm, run these steps yourself:

1. `infrahubctl branch create learning-pc-demo`
2. `infrahubctl object load sandbox/objects.yml --branch learning-pc-demo`
3. Open a proposed change from learning-pc-demo in the UI and read the diff.
4. Clean up: `infrahubctl branch delete learning-pc-demo`

## Check
1. Why did the diff show only your branch's edits?
2. What would a check have blocked here?
"""


def test_sandbox_safety_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=SANDBOX_LESSON, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert ok, msg


def test_sandbox_safety_merge_forbidden(tmp_path):
    merged = SANDBOX_LESSON.replace(
        "4. Clean up:", "4. `infrahubctl branch merge learning-pc-demo`\n5. Clean up:")
    ws = make_ws(tmp_path, lesson=merged, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "merge" in msg


def test_sandbox_safety_write_outside_learning_branch(tmp_path):
    stray = SANDBOX_LESSON.replace(
        "`infrahubctl object load sandbox/objects.yml --branch learning-pc-demo`",
        "`infrahubctl object load sandbox/objects.yml`")
    ws = make_ws(tmp_path, lesson=stray, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok


def test_sandbox_safety_no_opt_in_question(tmp_path):
    silent = SANDBOX_LESSON.replace(
        "This exercise writes to your instance. Shall we create a scratch branch for it?\n\n",
        "")
    ws = make_ws(tmp_path, lesson=silent, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "opt-in" in msg


def test_sandbox_safety_no_cleanup(tmp_path):
    dirty = SANDBOX_LESSON.replace(
        "4. Clean up: `infrahubctl branch delete learning-pc-demo`\n", "")
    ws = make_ws(tmp_path, lesson=dirty, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "delete" in msg


def test_sandbox_safety_warning_phrasing_pass(tmp_path):
    warned = SANDBOX_LESSON.replace(
        "## Check",
        "Never run `infrahubctl branch merge learning-pc-demo`; the "
        "learning branch is never merged.\n\n## Check",
    )
    ws = make_ws(tmp_path, lesson=warned, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert ok, msg


def test_sandbox_safety_ui_merge_imperative_step_fails(tmp_path):
    ui_merge = SANDBOX_LESSON.replace(
        "4. Clean up:",
        "4. Merge the proposed change in the UI to apply it to main.\n"
        "5. Clean up:",
    )
    ws = make_ws(tmp_path, lesson=ui_merge, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "merge" in msg


def test_sandbox_safety_mutating_command_in_explain_fails(tmp_path):
    stray_explain = SANDBOX_LESSON.replace(
        "See https://docs.infrahub.app/topics/proposed-change for details.",
        "See https://docs.infrahub.app/topics/proposed-change for details.\n"
        "For example: `infrahubctl object load sandbox/objects.yml`.",
    )
    ws = make_ws(tmp_path, lesson=stray_explain, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "mutating" in msg


def test_is_merge_violation_not_substring_in_note_still_flagged():
    # "not" is a substring of "note": a plain substring negation guard used
    # to silence this line entirely, hiding a real merge-into-main step.
    line = "3. Merge the proposed change into main - note the diff disappears."
    assert teaching_lib._is_merge_violation(line)


def test_is_merge_violation_negation_substring_in_another_or_nothing_still_flagged():
    assert teaching_lib._is_merge_violation(
        "5. Merge learning-pc-demo into another branch, nothing else needed."
    )


def test_sandbox_safety_merge_with_note_word_fails(tmp_path):
    merged = SANDBOX_LESSON.replace(
        "3. Open a proposed change from learning-pc-demo in the UI and read the diff.",
        "3. Merge the proposed change into main - note the diff disappears.",
    )
    ws = make_ws(tmp_path, lesson=merged, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "merge" in msg


def test_sandbox_safety_another_nothing_words_still_flagged(tmp_path):
    merged = SANDBOX_LESSON.replace(
        "4. Clean up:",
        "4. Merge learning-pc-demo into another branch; nothing else needed.\n"
        "5. Clean up:",
    )
    ws = make_ws(tmp_path, lesson=merged, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "merge" in msg


def test_own_artifacts_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["own-artifacts"](ws)
    assert ok, msg


def test_own_artifacts_generic_example_instead(tmp_path):
    generic = COMPLIANT_LESSON.replace("TestbedSensor", "MyNode").replace(
        "TestbedZone", "OtherNode").replace("TestbedRack", "ThirdNode")
    ws = make_ws(tmp_path, lesson=generic)
    ok, msg = teaching_lib.CHECKS["own-artifacts"](ws)
    assert not ok


def test_graduation_pointer_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON)
    ok, msg = teaching_lib.CHECKS["graduation-pointer"](ws)
    assert ok, msg


def test_graduation_pointer_missing(tmp_path):
    no_pointer = COMPLIANT_LESSON.replace(
        "Next step when you are ready: the infrahub-managing-schemas skill does\nthis work on real projects.\n",
        "")
    ws = make_ws(tmp_path, lesson=no_pointer)
    ok, msg = teaching_lib.CHECKS["graduation-pointer"](ws)
    assert not ok


OFF_MAP_LESSON = COMPLIANT_LESSON.replace(
    "# Lesson: schema relationships", "# Lesson: webhooks (off-map)"
).replace(
    "https://docs.infrahub.app/topics/schema",
    "https://docs.infrahub.app/topics/webhooks",
)


def test_off_map_lesson_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=OFF_MAP_LESSON, concept="webhooks")
    ok, msg = teaching_lib.CHECKS["off-map-lesson"](ws)
    assert ok, msg


def test_off_map_lesson_rejects_known_slug(tmp_path):
    ws = make_ws(tmp_path, lesson=OFF_MAP_LESSON, concept="schema")
    ok, msg = teaching_lib.CHECKS["off-map-lesson"](ws)
    assert not ok and "slug" in msg


def test_off_map_lesson_needs_docs_citation(tmp_path):
    uncited = OFF_MAP_LESSON.replace(
        "See https://docs.infrahub.app/topics/webhooks for the full model.", "")
    ws = make_ws(tmp_path, lesson=uncited, concept="webhooks")
    ok, msg = teaching_lib.CHECKS["off-map-lesson"](ws)
    assert not ok


def test_off_map_lesson_needs_structure(tmp_path):
    unstructured = OFF_MAP_LESSON.replace("## Check", "## Recap")
    ws = make_ws(tmp_path, lesson=unstructured, concept="webhooks")
    ok, msg = teaching_lib.CHECKS["off-map-lesson"](ws)
    assert not ok


COMPARISON_LINE_SOURCED = (
    "In NetBox, config contexts attach JSON data to devices by scope.\n"
    "**Comparison source:** https://docs.netbox.dev/en/stable/features/context-data/\n"
)
COMPARISON_LINE_UNVERIFIED = (
    "You described NetBox config contexts; I could not verify the NetBox\n"
    "side against its docs from here, so I am unsure of that half.\n"
    "**Comparison source:** unverified\n"
)


def _with_comparison(line: str) -> str:
    return COMPLIANT_LESSON.replace("## Exercise", line + "\n## Exercise")


def test_competitor_mapping_sourced_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=_with_comparison(COMPARISON_LINE_SOURCED))
    ok, msg = teaching_lib.CHECKS["competitor-mapping"](ws)
    assert ok, msg


def test_competitor_mapping_unverified_pass(tmp_path):
    ws = make_ws(tmp_path, lesson=_with_comparison(COMPARISON_LINE_UNVERIFIED))
    ok, msg = teaching_lib.CHECKS["competitor-mapping"](ws)
    assert ok, msg


def test_competitor_mapping_missing_marker(tmp_path):
    bare = COMPLIANT_LESSON.replace(
        "## Exercise", "In NetBox this is a config context.\n\n## Exercise")
    ws = make_ws(tmp_path, lesson=bare)
    ok, msg = teaching_lib.CHECKS["competitor-mapping"](ws)
    assert not ok and "Comparison source" in msg


def test_competitor_mapping_blog_source_rejected(tmp_path):
    blog = COMPARISON_LINE_SOURCED.replace(
        "https://docs.netbox.dev/en/stable/features/context-data/",
        "https://someblog.example.com/netbox-vs-infrahub")
    ws = make_ws(tmp_path, lesson=_with_comparison(blog))
    ok, msg = teaching_lib.CHECKS["competitor-mapping"](ws)
    assert not ok and "official" in msg


def test_competitor_mapping_infrahub_citation_still_required(tmp_path):
    no_infrahub = _with_comparison(COMPARISON_LINE_SOURCED).replace(
        "See https://docs.infrahub.app/topics/schema for the full model.", "")
    ws = make_ws(tmp_path, lesson=no_infrahub)
    ok, msg = teaching_lib.CHECKS["competitor-mapping"](ws)
    assert not ok


# --- Compliant, phrased differently -------------------------------------
#
# The false-fail direction: correct output that does not copy the shape of
# the rule's own example. A check that fails these grades wording.

VARIANT_LESSON = """Lesson - how attributes behave
=============================

## Probe
- Which of your two node kinds carries the most attributes?
- Have you set a default value on one before?
- What do you expect `unique: true` to reject?

## Explain
Attributes hold the values on a node. On `TestbedSensor` the `name`
attribute is unique, so a second sensor cannot reuse it; `TestbedZone`
declares its own. Read
[the schema topic](https://docs.infrahub.app/topics/schema#attributes)
for the full list of kinds.

Once you are past the basics, `infrahub-analyzing-data` is the skill that
queries these attributes on a live instance.

## Exercise
**Your task:**
Give `TestbedZone` a second attribute of your choosing, then say when you
want it reviewed.

## Check
- Why did the loader reject a duplicate name?
- Which attribute would you make unique next?
"""

VARIANT_SOLUTION = """Reference solution
==================

## Solution
```yaml
attributes:
  - name: floor
    kind: Number
    optional: true
```

## Verification
Loaded with `infrahubctl schema check schemas/testbed.yml` against the
in-memory validator: no errors, `TestbedZone.floor` resolves.
"""

VARIANT_PROGRESS = """|  Concept  |  Status  |  Last-Seen  |  Notes  |
| :--- | :--- | :--- | :--- |
|  menus  |  not-seen  |  2026-09-07  |  queued  |
|  schema  |  introduced  |  2026-09-09  |  hint ladder ran to reveal  |
"""


def test_probe_first_pass_variant(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, concept="objects")
    ok, msg = teaching_lib.CHECKS["probe-first"](ws)
    assert ok, msg


def test_structured_lessons_pass_variant(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, concept="objects")
    ok, msg = teaching_lib.CHECKS["structured-lessons"](ws)
    assert ok, msg


def test_cite_docs_pass_variant_markdown_link(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, concept="objects")
    ok, msg = teaching_lib.CHECKS["cite-docs"](ws)
    assert ok, msg


def test_own_artifacts_pass_variant(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, concept="objects")
    ok, msg = teaching_lib.CHECKS["own-artifacts"](ws)
    assert ok, msg


def test_graduation_pointer_pass_variant_analyzing_skill(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, concept="objects")
    ok, msg = teaching_lib.CHECKS["graduation-pointer"](ws)
    assert ok, msg


def test_learner_authors_pass_variant(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, solution=VARIANT_SOLUTION,
                 concept="objects")
    ok, msg = teaching_lib.CHECKS["learner-authors"](ws)
    assert ok, msg


def test_verified_solution_pass_variant(tmp_path):
    ws = make_ws(tmp_path, lesson=VARIANT_LESSON, solution=VARIANT_SOLUTION,
                 concept="objects")
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert ok, msg


def test_record_progress_pass_variant(tmp_path):
    ws = make_ws(tmp_path, progress=VARIANT_PROGRESS)
    ok, msg = teaching_lib.CHECKS["record-progress"](ws)
    assert ok, msg


def test_status_stays_introduced_pass_variant(tmp_path):
    ws = make_ws(tmp_path, progress=VARIANT_PROGRESS)
    ok, msg = teaching_lib.CHECKS["status-stays-introduced"](ws)
    assert ok, msg


def test_hint_before_solution_pass_variant_short_snippet(tmp_path):
    hint = ("Compare the two lines below and re-read your `peer` value:\n"
            "```yaml\npeer: <a node kind, not an attribute>\n```\n"
            "Which of your kinds belongs there?")
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON,
                 solution=COMPLIANT_SOLUTION, reply=hint)
    ok, msg = teaching_lib.CHECKS["hint-before-solution"](ws)
    assert ok, msg


def test_sandbox_safety_pass_variant(tmp_path):
    variant = SANDBOX_LESSON.replace(
        "This exercise writes to your instance. Shall we create a scratch branch for it?",
        "Happy for me to scope this to a throwaway branch you delete after?",
    ).replace(
        "1. `infrahubctl branch create learning-pc-demo`",
        "1. Create the sandbox first: `infrahubctl branch create learning-pc-demo`",
    )
    ws = make_ws(tmp_path, lesson=variant, concept="proposed-changes")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert ok, msg


def test_off_map_lesson_pass_variant(tmp_path):
    variant = VARIANT_LESSON.replace(
        "https://docs.infrahub.app/topics/schema#attributes",
        "https://docs.infrahub.app/topics/api-tokens",
    )
    ws = make_ws(tmp_path, lesson=variant, concept="api-tokens")
    ok, msg = teaching_lib.CHECKS["off-map-lesson"](ws)
    assert ok, msg


# --- The concept map is the single home for the slug list ----------------


def test_known_slugs_derives_from_the_concept_map():
    assert teaching_lib.known_slugs() == frozenset(
        {"foundations", "schema", "objects", "graphql", "branches",
         "repo-integration", "proposed-changes", "checks", "transforms",
         "generators", "menus"}
    )


def test_known_slugs_picks_up_a_new_map_row(tmp_path, monkeypatch):
    # A row added to the map has to reach the check without a grader edit.
    fake_map = tmp_path / "concept-map.md"
    fake_map.write_text(
        "| # | Concept | Prerequisites |\n| --- | --- | --- |\n"
        "| 1 | schema | none |\n| 2 | webhooks | schema |\n"
    )
    monkeypatch.setattr(teaching_lib, "CONCEPT_MAP", fake_map)
    assert teaching_lib.known_slugs() == frozenset({"schema", "webhooks"})
    ws = make_ws(tmp_path, lesson=OFF_MAP_LESSON, concept="webhooks")
    ok, msg = teaching_lib.CHECKS["off-map-lesson"](ws)
    assert not ok and "slug" in msg


def test_known_slugs_raises_when_map_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(teaching_lib, "CONCEPT_MAP", tmp_path / "gone.md")
    try:
        teaching_lib.known_slugs()
    except FileNotFoundError as exc:
        assert "concept map" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_known_slugs_raises_when_no_rows_parse(tmp_path, monkeypatch):
    empty = tmp_path / "concept-map.md"
    empty.write_text("# Concept Map\n\nprose only, no table rows\n")
    monkeypatch.setattr(teaching_lib, "CONCEPT_MAP", empty)
    try:
        teaching_lib.known_slugs()
    except ValueError as exc:
        assert "no numbered concept rows" in str(exc)
    else:
        raise AssertionError("expected ValueError")


# --- A compliant first lesson must not launder a violating second --------
#
# "schema" sorts before "transforms", so the violation is always second.


def _two_lessons(tmp_path, second):
    make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=COMPLIANT_SOLUTION,
            concept="schema")
    return make_ws(tmp_path, lesson=second, solution=COMPLIANT_SOLUTION,
                   concept="transforms")


def test_probe_first_second_lesson_violation_fails(tmp_path):
    ws = _two_lessons(tmp_path, COMPLIANT_LESSON.replace(
        "2. Have you used foreign keys in a database before?", ""))
    ok, msg = teaching_lib.CHECKS["probe-first"](ws)
    assert not ok and "transforms.md" in msg


def test_cite_docs_second_lesson_violation_fails(tmp_path):
    ws = _two_lessons(tmp_path, COMPLIANT_LESSON.replace(
        "See https://docs.infrahub.app/topics/schema for the full model.", ""))
    ok, msg = teaching_lib.CHECKS["cite-docs"](ws)
    assert not ok and "transforms.md" in msg


def test_structured_lessons_second_lesson_violation_fails(tmp_path):
    ws = _two_lessons(tmp_path, COMPLIANT_LESSON.replace(
        "## Check", "## Recap"))
    ok, msg = teaching_lib.CHECKS["structured-lessons"](ws)
    assert not ok and "transforms.md" in msg


def test_learner_authors_second_lesson_violation_fails(tmp_path):
    ws = _two_lessons(tmp_path, COMPLIANT_LESSON.replace(
        "**Your task:**", "Try this:"))
    ok, msg = teaching_lib.CHECKS["learner-authors"](ws)
    assert not ok and "transforms.md" in msg


def test_own_artifacts_second_lesson_violation_fails(tmp_path):
    ws = _two_lessons(tmp_path, COMPLIANT_LESSON.replace(
        "TestbedSensor", "MyNode").replace("TestbedZone", "OtherNode"))
    ok, msg = teaching_lib.CHECKS["own-artifacts"](ws)
    assert not ok and "transforms.md" in msg


def test_graduation_pointer_second_lesson_violation_fails(tmp_path):
    ws = _two_lessons(tmp_path, COMPLIANT_LESSON.replace(
        "Next step when you are ready: the infrahub-managing-schemas skill does\nthis work on real projects.\n",
        ""))
    ok, msg = teaching_lib.CHECKS["graduation-pointer"](ws)
    assert not ok and "transforms.md" in msg


def test_verified_solution_second_lesson_unverified_fails(tmp_path):
    make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=COMPLIANT_SOLUTION,
            concept="schema")
    vacuous = COMPLIANT_SOLUTION.split("## Verification")[0] + (
        "## Verification\nThis should work.\n"
    )
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=vacuous,
                 concept="transforms")
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert not ok and "transforms.md" in msg


def test_verified_solution_second_lesson_missing_solution_fails(tmp_path):
    make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=COMPLIANT_SOLUTION,
            concept="schema")
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON, concept="transforms")
    ok, msg = teaching_lib.CHECKS["verified-solution"](ws)
    assert not ok and "transforms.md" in msg


def test_sandbox_safety_second_lesson_merge_fails(tmp_path):
    make_ws(tmp_path, lesson=SANDBOX_LESSON, concept="proposed-changes")
    merged = SANDBOX_LESSON.replace(
        "4. Clean up:",
        "4. `infrahubctl branch merge learning-pc-demo`\n5. Clean up:")
    ws = make_ws(tmp_path, lesson=merged, concept="transforms")
    ok, msg = teaching_lib.CHECKS["sandbox-safety"](ws)
    assert not ok and "transforms.md" in msg


def test_competitor_mapping_second_comparison_unsourced_fails(tmp_path):
    make_ws(tmp_path, lesson=_with_comparison(COMPARISON_LINE_SOURCED),
            concept="schema")
    bare = COMPLIANT_LESSON.replace(
        "## Exercise", "In Nautobot this is a config context.\n\n## Exercise")
    ws = make_ws(tmp_path, lesson=bare, concept="transforms")
    ok, msg = teaching_lib.CHECKS["competitor-mapping"](ws)
    assert not ok and "transforms.md" in msg


def test_hint_before_solution_leaks_second_lesson_solution(tmp_path):
    make_ws(tmp_path, lesson=COMPLIANT_LESSON, concept="schema")
    other_solution = """# Solution: transforms

## Solution
```python
def transform(data):
    return {"hostname": data["TestbedSensor"]["name"]}
```

## Verification
Ran `infrahubctl transform sensor_export`: rendered without error.
"""
    spoiler = ('Here you go:\n```python\ndef transform(data):\n'
               '    return {"hostname": data["TestbedSensor"]["name"]}\n```\n')
    ws = make_ws(tmp_path, lesson=COMPLIANT_LESSON, solution=other_solution,
                 reply=spoiler, concept="transforms")
    ok, msg = teaching_lib.CHECKS["hint-before-solution"](ws)
    assert not ok and "transforms.md" in msg
