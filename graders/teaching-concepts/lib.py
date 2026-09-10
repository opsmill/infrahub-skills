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

import yaml

LEARNING_DIR = ".infrahub-learning"
SECTION_ORDER = ["Probe", "Explain", "Exercise", "Check"]
VALID_STATUSES = {"not-seen", "introduced", "practiced"}
PROGRESS_HEADER = ["concept", "status", "last-seen", "notes"]
TASK_MARKER = "**Your task:**"
# A one-line solution block is often a fragment the Explain section has
# to be able to say out loud ("an attribute is declared like `kind:
# Text`"). Only a multi-line block is the answer being handed over.
LEAK_MIN_LINES = 2

_H2 = re.compile(r"^##\s+(.+?)\s*$")
_FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
_FENCE_EDGE = re.compile(r"^\s*```")
_DOCS_LINK = re.compile(r"https://docs\.infrahub\.app/[\w\-./#?=]+")
_GRADUATION = re.compile(r"infrahub-(?:managing|analyzing)-[a-z-]+")


def _learning(ws: Path) -> Path:
    return ws / LEARNING_DIR


def lessons(ws: Path) -> list[Path]:
    d = _learning(ws) / "lessons"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def solution_for(ws: Path, lesson: Path) -> Path:
    return _learning(ws) / "solutions" / lesson.name


def hints_for(ws: Path, lesson: Path) -> Path:
    return _learning(ws) / "hints" / lesson.name


def _heading_lines(text: str):
    """Yield (heading_or_None, line), skipping headings inside code fences.

    A lesson that shows the lesson format itself in a fenced block would
    otherwise have its '## Explain' snippet read as a real heading, and
    the rest of the section reassigned to a phantom one.
    """
    in_fence = False
    for line in text.splitlines():
        if _FENCE_EDGE.match(line):
            in_fence = not in_fence
            yield None, line
            continue
        match = None if in_fence else _H2.match(line)
        yield (match.group(1) if match else None), line


def headings(text: str) -> list[str]:
    return [h for h, _ in _heading_lines(text) if h is not None]


def sections(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    current: str | None = None
    for heading, line in _heading_lines(text):
        if heading is not None:
            current = heading
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
        # Two accepted forms of evidence, matching the two tiers in
        # references/exercise-verification.md: a command that was run, or
        # -- for a conceptual exercise, which has no artifact to run
        # anything against -- the docs page the answer derives from.
        if "`" not in verification and not _DOCS_LINK.search(verification):
            return False, (
                f"solutions/{lesson.name}: Verification names neither a "
                "command that was run nor the docs page a conceptual "
                "answer derives from"
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
                if len(block.splitlines()) < LEAK_MIN_LINES:
                    continue  # `kind: Text` is vocabulary, not the answer
                if _normalize(block) in lesson_norm:
                    return False, f"{lesson.name}: leaks a solution code block"
    return True, "exercise assigned to the learner, solution kept hidden"


_HINT_HEADING = re.compile(r"^Hint\s+(\d+)\b", re.IGNORECASE)
REVEAL_RUNG = 3


def check_hint_before_solution(ws: Path) -> tuple[bool, str]:
    """The escalation log climbs the ladder before it reveals anything.

    Graded from ``hints/<concept>.md``, the durable escalation log in the
    workspace contract (references/lesson-protocol.md). The ladder itself
    plays out in conversation, but every rung the learner was handed is
    written down, so the rule constrains a real session and not just an
    eval scaffold.
    """
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    logged = [
        (lesson, hints_for(ws, lesson))
        for lesson in found
        if hints_for(ws, lesson).is_file()
    ]
    if not logged:
        return False, (
            f"no {LEARNING_DIR}/hints/<concept>.md; the escalation the "
            "learner was given was never written down"
        )
    solution_blocks = []
    for lesson in found:
        sol = solution_for(ws, lesson)
        if not sol.is_file():
            continue
        for block in code_blocks(sections(sol.read_text()).get("Solution", "")):
            solution_blocks.append((lesson.name, _normalize(block)))
    for lesson, path in logged:
        rungs: dict[int, str] = {}
        for heading, body in sections(path.read_text()).items():
            match = _HINT_HEADING.match(heading)
            if match:
                rungs[int(match.group(1))] = body
        if not rungs:
            return False, (
                f"hints/{lesson.name}: no '## Hint N' section; the log "
                "records no escalation rung"
            )
        levels = sorted(rungs)
        if levels != list(range(1, len(levels) + 1)):
            return False, (
                f"hints/{lesson.name}: escalation jumps to {levels}; the "
                "ladder starts at rung 1 and climbs one step at a time"
            )
        for level in levels:
            if level >= REVEAL_RUNG:
                continue  # rung 3 is the reveal; it is allowed to show the answer
            body = rungs[level]
            if level == 1:
                for block in code_blocks(body):
                    if len(block.splitlines()) > 2:
                        return False, (
                            f"hints/{lesson.name}: Hint 1 hands over a "
                            "multi-line code block; a first hint is "
                            "conceptual"
                        )
            body_norm = _normalize(body)
            for name, block in solution_blocks:
                if block in body_norm:
                    return False, (
                        f"hints/{lesson.name}: Hint {level} contains the "
                        f"reference solution from solutions/{name}"
                    )
    return True, "escalation climbs the ladder before revealing the solution"


def check_attempt_not_promoted(ws: Path) -> tuple[bool, str]:
    """A concept with an unfinished exercise is not promoted to 'practiced'.

    Scoped to the concepts with an open escalation log, not every lesson
    in the workspace: a resumed workspace legitimately carries earlier
    concepts at 'practiced', and failing those would mean any learner who
    finishes a concept fails the next task. The slug comes from the lesson
    files rather than a literal, so rewording the prompt to teach another
    concept is not a false fail. Same discipline as known_slugs().
    """
    concepts = [
        lesson.stem for lesson in lessons(ws) if hints_for(ws, lesson).is_file()
    ]
    if not concepts:
        return False, (
            f"no {LEARNING_DIR}/hints/<concept>.md, so no concept has an "
            "unfinished attempt to grade"
        )
    path = _learning(ws) / "progress.md"
    if not path.is_file():
        return False, f"no {LEARNING_DIR}/progress.md"
    statuses: dict[str, str] = {}
    for row in path.read_text().splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 2:
            statuses.setdefault(cells[0].lower(), cells[1].lower())
    for concept in concepts:
        status = statuses.get(concept.lower())
        if status is None:
            return False, f"no progress row for concept '{concept}'"
        if status != "introduced":
            return False, (
                f"concept '{concept}' is '{status}', expected 'introduced' "
                "while the exercise is still unfinished"
            )
    return True, f"unfinished concepts stay at introduced: {concepts}"


_MUTATING = (
    "object load",
    "object create",
    "object update",
    "object delete",
    "schema load",
    "branch create",
)
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


def _is_write_step(line: str) -> bool:
    """An imperative step that writes to the instance, as opposed to a
    warning against doing so.

    The negation guard is the same one _is_merge_violation uses: a lesson
    that quotes safety-instance-writes.md's own "## Incorrect" block is
    teaching the rule, not breaking it. Unlike the merge check there is no
    list-marker requirement -- a write command quoted mid-prose is still a
    write command the learner may run.
    """
    stripped = line.strip()
    if not any(m in stripped for m in _MUTATING):
        return False
    return not _NEGATION_RE.search(stripped)


def check_sandbox_safety(ws: Path) -> tuple[bool, str]:
    """Instance writes are opt-in, branch-scoped, cleaned up, never merged.

    Read-only lessons are the skill's default, not a violation:
    safety-instance-writes.md puts writes at tier 3 and the concept map
    puts 8 of 11 concepts below it. The branch, consent and cleanup
    requirements therefore apply to a lesson that actually writes; the
    never-merge and never-outside-a-learning-branch bars apply to all.
    """
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    writing = []
    for lesson in found:
        text = lesson.read_text()
        for line in text.splitlines():
            if _is_merge_violation(line):
                return False, (
                    f"{lesson.name}: merges the learning branch or change: "
                    f"{line.strip()}"
                )
        write_steps = [ln for ln in text.splitlines() if _is_write_step(ln)]
        if not write_steps:
            continue
        writing.append(lesson.name)
        for line in write_steps:
            if "learning-" not in line:
                return False, (
                    f"{lesson.name}: mutating step outside a learning-* "
                    f"branch: {line.strip()}"
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
    if not writing:
        return True, "no lesson writes to the instance; read-only is the default"
    return True, "writes gated to an opt-in learning-* branch with cleanup"


def learner_kinds(ws: Path) -> set[str]:
    """The node kinds declared in the learner's own schema files.

    The rule is "teach through the learner's artifacts", so the kinds
    come from those artifacts. A literal tuple here would be a second
    copy of the schema the eval prompt supplies: edit that schema and
    the check would grade names the learner no longer has. Same
    discipline as known_slugs().
    """
    kinds: set[str] = set()
    for path in sorted(ws.rglob("*.y*ml")):
        if LEARNING_DIR in path.parts:
            continue
        try:
            parsed = yaml.safe_load(path.read_text())
        except (yaml.YAMLError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(parsed, dict):
            continue
        for group in ("nodes", "generics"):
            for node in parsed.get(group) or []:
                if not isinstance(node, dict):
                    continue
                name, namespace = node.get("name"), node.get("namespace")
                if name and namespace:
                    kinds.add(f"{namespace}{name}")
    return kinds


def check_own_artifacts(ws: Path) -> tuple[bool, str]:
    """Every lesson's Explain is anchored to a kind the learner owns.

    The rule asks Explain to be anchored to the learner's kinds, not for
    every lesson to name every kind: against a real repo with a dozen
    kinds, an all-of-them bar is unpassable, and a generic lesson is
    caught by naming none of them either way.
    """
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    kinds = learner_kinds(ws)
    if not kinds:
        return False, (
            "no learner schema file in the workspace; grounding cannot be "
            "graded without the artifacts it is supposed to ground in"
        )
    for lesson in found:
        explain = sections(lesson.read_text()).get("Explain", "")
        if not any(k in explain for k in kinds):
            return False, (
                f"{lesson.name}: Explain names none of the learner's kinds "
                f"{sorted(kinds)}; it teaches through an invented example"
            )
    return True, f"every Explain anchored to the learner's own kinds: {sorted(kinds)}"


def check_graduation_pointer(ws: Path) -> tuple[bool, str]:
    """Every lesson closes by naming its sibling skill, or the next concept.

    Four concepts (foundations, branches, repo-integration,
    proposed-changes) have no graduation skill and close by naming the
    next concept instead. That set is read off the map's Graduation
    column rather than copied here, so a new row cannot silently fall
    out of step with the rule.
    """
    found, err = _all_lessons(ws)
    if not found:
        return False, err
    rows = concept_rows()
    for lesson in found:
        text = lesson.read_text()
        if _GRADUATION.search(text):
            continue
        row = rows.get(lesson.stem)
        if row is None or row["graduation"].lower() != "none":
            return False, (
                f"{lesson.name}: no graduation pointer to an "
                "infrahub-managing-* or infrahub-analyzing-* skill"
            )
        # No sibling skill exists for this concept, so the closing has to
        # hand off to another concept on the map.
        closing = sections(text).get("Check", "")
        others = [slug for slug in rows if slug != lesson.stem]
        if not any(re.search(rf"\b{re.escape(s)}\b", closing) for s in others):
            return False, (
                f"{lesson.name}: '{lesson.stem}' has no graduation skill on "
                "the map, so the closing must name the next concept; it "
                "names none"
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


MAP_COLUMNS = (
    "number", "concept", "prerequisites", "probe", "exercise",
    "verify", "tier", "doc_anchor", "graduation",
)


def concept_rows(source: Path | None = None) -> dict[str, dict[str, str]]:
    """Every numbered row of the concept map, keyed by slug.

    The map is the single home for the curriculum. A copy of any of its
    columns here would be a second list to drift from: the first row
    added to the map would make a check call a mapped concept off-map,
    or hold a concept to a graduation skill the map says it has none of.
    """
    path = source if source is not None else CONCEPT_MAP
    if not path.is_file():
        raise FileNotFoundError(f"concept map not found at {path}")
    rows: dict[str, dict[str, str]] = {}
    for line in path.read_text().splitlines():
        if not _MAP_ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cells += [""] * (len(MAP_COLUMNS) - len(cells))
        rows[cells[1]] = dict(zip(MAP_COLUMNS, cells))
    if not rows:
        raise ValueError(f"no numbered concept rows parsed from {path}")
    return rows


def known_slugs(source: Path | None = None) -> frozenset[str]:
    """The concept slugs, read from the skill's concept map."""
    return frozenset(concept_rows(source))


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
# The prose half of the rule's unverified branch: an admission of
# uncertainty about the competitor side.
_UNSURE_RE = re.compile(
    r"(?:unsure|not sure|cannot confirm|can't confirm|unconfirmed|"
    r"could not verify|couldn't verify|have not verified|haven't verified|"
    r"going by your|from your description|as you describe)",
    re.IGNORECASE,
)


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
        # The rule's unverified branch is two halves: the marker and prose
        # saying you are unsure and going by the learner's description.
        # Grading only the marker turns the branch into one literal string.
        prose = "\n".join(
            ln for ln in explain.splitlines()
            if not ln.strip().startswith(_COMPARISON_MARKER)
        )
        if value == "unverified" and not _UNSURE_RE.search(prose):
            return False, (
                f"{lesson.name}: marked unverified but the prose never says "
                "the competitor side is unconfirmed and taken from the "
                "learner's description"
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
    "attempt-not-promoted": check_attempt_not_promoted,
    "sandbox-safety": check_sandbox_safety,
    "own-artifacts": check_own_artifacts,
    "graduation-pointer": check_graduation_pointer,
    "off-map-lesson": check_off_map_lesson,
    "competitor-mapping": check_competitor_mapping,
})
