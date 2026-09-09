#!/usr/bin/env python3
"""Shared grader library for infrahub-teaching-concepts skill evaluations.

Parses the .infrahub-learning/ workspace a lesson session leaves behind and
runs deterministic assertion checks over it. Exposes a CHECKS registry and
run_checks(), which returns skillgrade JSON:

    {"score": 0.5, "details": "...", "checks": [{"name", "passed", "message"}]}

Checks are deterministic: no LLM, no network. The values here mirror the
workspace contract in
skills/infrahub-teaching-concepts/references/lesson-protocol.md.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

LEARNING_DIR = ".infrahub-learning"
SECTION_ORDER = ["Probe", "Explain", "Exercise", "Check"]
VALID_STATUSES = {"not-seen", "introduced", "practiced"}
PROGRESS_HEADER = ["concept", "status", "last-seen", "notes"]
TASK_MARKER = "**Your task:**"

_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
_DOCS_LINK = re.compile(r"https://docs\.infrahub\.app/[\w\-./#?=]+")
_GRADUATION = re.compile(r"infrahub-(?:managing|analyzing)-[a-z-]+")


def _learning(ws: Path) -> Path:
    return ws / LEARNING_DIR


def lessons(ws: Path) -> list[Path]:
    d = _learning(ws) / "lessons"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def solution_for(ws: Path, lesson: Path) -> Path:
    return _learning(ws) / "solutions" / lesson.name


def headings(text: str) -> list[str]:
    return _H2.findall(text)


def sections(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1)
            parts[current] = ""
        elif current is not None:
            parts[current] += line + "\n"
    return parts


def code_blocks(text: str) -> list[str]:
    return [m.strip() for m in _FENCE.findall(text) if m.strip()]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _first_lesson(ws: Path) -> tuple[Path | None, str]:
    found = lessons(ws)
    if not found:
        return None, f"no lesson file under {LEARNING_DIR}/lessons/"
    return found[0], ""


def _all_lessons(ws: Path) -> tuple[list[Path], str]:
    """Every lesson in the workspace, for checks that bind to all of them.

    Grading only ``lessons()[0]`` lets a compliant first lesson launder a
    violating second one.
    """
    found = lessons(ws)
    if not found:
        return [], f"no lesson file under {LEARNING_DIR}/lessons/"
    return found, ""


def check_structured_lessons(ws: Path) -> tuple[bool, str]:
    """Every lesson has Probe, Explain, Exercise, Check headings in order."""
    found = lessons(ws)
    if not found:
        return False, f"no lesson file under {LEARNING_DIR}/lessons/"
    for lesson in found:
        heads = headings(lesson.read_text())
        positions = []
        for name in SECTION_ORDER:
            if name not in heads:
                return False, f"{lesson.name}: missing '## {name}' section"
            positions.append(heads.index(name))
        if positions != sorted(positions):
            return False, f"{lesson.name}: sections out of order: {heads}"
    return True, "all lessons follow Probe/Explain/Exercise/Check"


def check_probe_first(ws: Path) -> tuple[bool, str]:
    """Probe precedes Explain and holds 2-3 questions, in every lesson."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        text = lesson.read_text()
        heads = headings(text)
        if "Probe" not in heads or "Explain" not in heads:
            return False, f"{lesson.name}: needs both Probe and Explain sections"
        if heads.index("Probe") > heads.index("Explain"):
            return False, f"{lesson.name}: Probe appears after Explain"
        probe = sections(text).get("Probe", "")
        questions = [ln for ln in probe.splitlines() if ln.strip().endswith("?")]
        if not 2 <= len(questions) <= 3:
            return False, (
                f"{lesson.name}: Probe has {len(questions)} question lines, "
                "expected 2-3"
            )
    return True, "probe precedes explanation with 2-3 questions"


def check_cite_docs(ws: Path) -> tuple[bool, str]:
    """Every lesson's Explain section links to docs.infrahub.app."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        explain = sections(lesson.read_text()).get("Explain", "")
        if not _DOCS_LINK.search(explain):
            return False, f"{lesson.name}: Explain has no docs.infrahub.app link"
    return True, "explanation carries a docs anchor"


def check_record_progress(ws: Path) -> tuple[bool, str]:
    """progress.md exists with the exact header and valid statuses."""
    path = _learning(ws) / "progress.md"
    if not path.is_file():
        return False, f"no {LEARNING_DIR}/progress.md"
    rows = [r for r in path.read_text().splitlines() if r.strip().startswith("|")]
    if not rows:
        return False, "progress.md holds no table"
    header = [c.strip().lower() for c in rows[0].strip().strip("|").split("|")]
    if header != PROGRESS_HEADER:
        return False, f"header is {header}, expected {PROGRESS_HEADER}"
    data_rows = [r for r in rows[2:] if r.replace("|", "").replace("-", "").strip()]
    if not data_rows:
        return False, "progress.md has no concept rows"
    for row in data_rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] not in VALID_STATUSES:
            return False, f"invalid status '{cells[1]}'"
    return True, "progress.md well formed"


def check_verified_solution(ws: Path) -> tuple[bool, str]:
    """Every lesson has a hidden solution carrying verification evidence."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        sol = solution_for(ws, lesson)
        if not sol.is_file():
            return False, f"no reference solution at solutions/{lesson.name}"
        parts = sections(sol.read_text())
        if "Solution" not in parts or not code_blocks(parts["Solution"]):
            return False, (
                f"solutions/{lesson.name}: needs a '## Solution' with a "
                "code block"
            )
        verification = parts.get("Verification", "").strip()
        if not verification:
            return False, (
                f"solutions/{lesson.name}: needs a non-empty '## Verification'"
            )
        lowered = verification.lower()
        if "should work" in lowered or "looks correct" in lowered:
            return False, (
                f"solutions/{lesson.name}: Verification is a vacuous "
                "assurance, not evidence"
            )
        if "`" not in verification:
            return False, (
                f"solutions/{lesson.name}: Verification names no command; "
                "nothing was actually run"
            )
    return True, "reference solution present with verification evidence"


def check_learner_authors(ws: Path) -> tuple[bool, str]:
    """Every exercise is assigned to the learner and leaks no solution."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        text = lesson.read_text()
        exercise = sections(text).get("Exercise", "")
        if TASK_MARKER not in exercise:
            return False, (
                f"{lesson.name}: Exercise lacks the '{TASK_MARKER}' "
                "assignment marker"
            )
        sol = solution_for(ws, lesson)
        if sol.is_file():
            sol_blocks = code_blocks(
                sections(sol.read_text()).get("Solution", "")
            )
            lesson_norm = _normalize(text)
            for block in sol_blocks:
                if _normalize(block) in lesson_norm:
                    return False, f"{lesson.name}: leaks a solution code block"
    return True, "exercise assigned to the learner, solution kept hidden"


def check_hint_before_solution(ws: Path) -> tuple[bool, str]:
    """A stuck-learner reply is a hint, not the answer."""
    path = ws / "reply.md"
    if not path.is_file():
        return False, "no reply.md written for the stuck learner"
    text = path.read_text()
    for block in code_blocks(text):
        if len(block.splitlines()) > 2:
            return False, "reply hands over a multi-line code block; a first hint must not be the solution"
    reply_norm = _normalize(text)
    for lesson in lessons(ws):
        sol = solution_for(ws, lesson)
        if not sol.is_file():
            continue
        for block in code_blocks(sections(sol.read_text()).get("Solution", "")):
            if _normalize(block) in reply_norm:
                return False, (
                    f"reply contains the reference solution from "
                    f"solutions/{lesson.name}"
                )
    return True, "reply is a hint, not the solution"


def check_status_stays_introduced(ws: Path) -> tuple[bool, str]:
    """After a solution reveal, the concept stays at 'introduced'."""
    path = _learning(ws) / "progress.md"
    if not path.is_file():
        return False, f"no {LEARNING_DIR}/progress.md"
    for row in path.read_text().splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == "schema":
            if cells[1] == "introduced":
                return True, "revealed concept stays at introduced"
            return False, f"concept 'schema' is '{cells[1]}', expected 'introduced' after a solution reveal"
    return False, "no progress row for concept 'schema'"


FIXTURE_KINDS = ("TestbedSensor", "TestbedZone")
_MUTATING = ("object load", "schema load", "object update", "branch create")
# Word-bounded so "not" does not match inside "note", "another", "nothing",
# or "annotate": a substring check silenced genuine violations sitting next
# to those words.
_NEGATION_RE = re.compile(r"\b(?:never|not|don't|do not)\b", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^(?:\d+\.|[-*])\s")


def _is_merge_violation(line: str) -> bool:
    """An imperative step that merges the learning branch or a proposed
    change, as opposed to a warning against doing so."""
    stripped = line.strip()
    lower = stripped.lower()
    if "merge" not in lower:
        return False
    if not _LIST_MARKER.match(stripped):
        return False
    if _NEGATION_RE.search(stripped):
        return False
    references_target = "learning-" in lower or (
        "proposed change" in lower and ("appl" in lower or "main" in lower)
    )
    return references_target


def check_sandbox_safety(ws: Path) -> tuple[bool, str]:
    """Instance writes are opt-in, branch-scoped, cleaned up, never merged."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        text = lesson.read_text()
        for line in text.splitlines():
            if _is_merge_violation(line):
                return False, (
                    f"{lesson.name}: merges the learning branch or change: "
                    f"{line.strip()}"
                )
        exercise = sections(text).get("Exercise", "")
        if "learning-" not in exercise:
            return False, f"{lesson.name}: exercise names no learning-* branch"
        opt_in = any(
            "?" in line and "branch" in line.lower()
            for line in exercise.splitlines()
        )
        if not opt_in:
            return False, (
                f"{lesson.name}: no opt-in question before instance writes"
            )
        if "branch delete" not in exercise:
            return False, (
                f"{lesson.name}: no cleanup step; expected a branch delete"
            )
        for line in text.splitlines():
            if any(m in line for m in _MUTATING) and "learning-" not in line:
                return False, (
                    f"{lesson.name}: mutating step outside a learning-* "
                    f"branch: {line.strip()}"
                )
    return True, "writes gated to an opt-in learning-* branch with cleanup"


def check_own_artifacts(ws: Path) -> tuple[bool, str]:
    """Every lesson teaches through the learner's fixture nodes."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        text = lesson.read_text()
        missing = [k for k in FIXTURE_KINDS if k not in text]
        if missing:
            return False, (
                f"{lesson.name}: never references the learner's nodes: "
                f"{missing}"
            )
    return True, "lesson grounded in the learner's own schema"


def check_graduation_pointer(ws: Path) -> tuple[bool, str]:
    """Every lesson names the sibling skill that does this work for real."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    for lesson in found:
        if not _GRADUATION.search(lesson.read_text()):
            return False, (
                f"{lesson.name}: no graduation pointer to an "
                "infrahub-managing-* or infrahub-analyzing-* skill"
            )
    return True, "graduation pointer present"


CONCEPT_MAP = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "infrahub-teaching-concepts"
    / "references"
    / "concept-map.md"
)
_MAP_ROW = re.compile(r"^\|\s*\d+\s*\|\s*([a-z][a-z0-9-]*)\s*\|")


def known_slugs(source: Path | None = None) -> frozenset[str]:
    """The concept slugs, read from the skill's concept map.

    The map is the single home for the curriculum. A copy of the slug list
    here would be a second list to drift from: the first row added to the
    map would make this check call a mapped concept off-map.
    """
    path = source if source is not None else CONCEPT_MAP
    if not path.is_file():
        raise FileNotFoundError(f"concept map not found at {path}")
    slugs = {m.group(1) for m in map(_MAP_ROW.match, path.read_text().splitlines()) if m}
    if not slugs:
        raise ValueError(f"no numbered concept rows parsed from {path}")
    return frozenset(slugs)


def check_off_map_lesson(ws: Path) -> tuple[bool, str]:
    """An off-map concept gets a docs-grounded lesson under its own slug."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    mapped = known_slugs()
    off_map = [lesson for lesson in found if lesson.stem not in mapped]
    if not off_map:
        return False, (
            f"every lesson slug is on the concept map ({[p.stem for p in found]}); "
            "expected an off-map slug for this topic"
        )
    structured, msg = check_structured_lessons(ws)
    if not structured:
        return False, msg
    cited, msg = check_cite_docs(ws)
    if not cited:
        return False, msg
    return True, "off-map lesson structured and docs-grounded"


# The rule file is the home for this allowlist; see
# skills/infrahub-teaching-concepts/rules/grounding-competitor-mapping.md.
COMPETITOR_DOC_HOSTS = (
    "docs.netbox.dev",
    "netboxlabs.com/docs",
    "docs.nautobot.com",
)
_COMPETITOR_RE = re.compile(r"\b(?:netbox|nautobot)\b", re.IGNORECASE)
_COMPARISON_MARKER = "**Comparison source:**"


def check_competitor_mapping(ws: Path) -> tuple[bool, str]:
    """Every comparing lesson is officially sourced or declared unverified."""
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    comparing = [
        lesson for lesson in found
        if _COMPETITOR_RE.search(sections(lesson.read_text()).get("Explain", ""))
    ]
    if not comparing:
        return False, (
            "no lesson Explain names a competitor; expected a translation "
            "lesson for this topic"
        )
    for lesson in comparing:
        explain = sections(lesson.read_text()).get("Explain", "")
        marker_lines = [
            ln for ln in explain.splitlines()
            if ln.strip().startswith(_COMPARISON_MARKER)
        ]
        if not marker_lines:
            return False, (
                f"{lesson.name}: Explain lacks a '{_COMPARISON_MARKER}' line"
            )
        value = marker_lines[0].strip()[len(_COMPARISON_MARKER):].strip()
        if value != "unverified" and not any(
            h in value for h in COMPETITOR_DOC_HOSTS
        ):
            return False, (
                f"{lesson.name}: comparison source is neither an official "
                f"competitor docs URL nor 'unverified': {value}"
            )
        if not _DOCS_LINK.search(explain):
            return False, (
                f"{lesson.name}: Explain lacks the Infrahub-side "
                "docs.infrahub.app link"
            )
    return True, "comparison sourced from official docs or declared unverified"


CHECKS: dict[str, Callable[[Path], tuple[bool, str]]] = {}


def run_checks(names: list[str], workspace: Path) -> dict:
    results = []
    for name in names:
        fn = CHECKS[name]
        try:
            passed, message = fn(workspace)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed check
            passed, message = False, f"check crashed: {exc}"
        results.append({"name": name, "passed": passed, "message": message})
    score = sum(r["passed"] for r in results) / len(results) if results else 0.0
    failures = "; ".join(
        f"{r['name']}: {r['message']}" for r in results if not r["passed"]
    )
    return {
        "score": round(score, 2),
        "details": failures or "all checks passed",
        "checks": results,
    }


CHECKS.update({
    "structured-lessons": check_structured_lessons,
    "probe-first": check_probe_first,
    "cite-docs": check_cite_docs,
    "record-progress": check_record_progress,
    "verified-solution": check_verified_solution,
    "learner-authors": check_learner_authors,
    "hint-before-solution": check_hint_before_solution,
    "status-stays-introduced": check_status_stays_introduced,
    "sandbox-safety": check_sandbox_safety,
    "own-artifacts": check_own_artifacts,
    "graduation-pointer": check_graduation_pointer,
    "off-map-lesson": check_off_map_lesson,
    "competitor-mapping": check_competitor_mapping,
})
