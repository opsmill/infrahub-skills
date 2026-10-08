#!/usr/bin/env python3
"""Shared grader library for infrahub-designing-models skill evaluations.

Two artifacts are graded:

- ``output_dir/answer.md``: the next message of an interview, which must be
  exactly one question block (rule interview-one-question-recommended).
- ``design-brief.md``: the design brief the skill writes at the end of a
  session, under ``specs/<design-slug>/`` when the repository uses spec-kit
  and ``docs/designs/<design-slug>/`` when it does not (rules
  interview-inputs-digested,
  scope-split-before-data-layer, brief-sketch-rows-complete,
  brief-decision-provenance).

Every check parses headings, tables and line structure; none of them
substring-matches the answer. Exposes a CHECKS registry and run_checks(),
which returns skillgrade JSON:

    {"score": 0.5, "details": "...", "checks": [{"name", "passed", "message"}]}

Checks are deterministic: no LLM, no network.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import yaml

ANSWER_PATH = Path("output_dir") / "answer.md"
# Either location is valid; which one is right depends on the repository,
# and a session writes exactly one brief.
BRIEF_GLOBS = ("specs/*/design-brief.md", "docs/designs/*/design-brief.md")

SKETCH_HEADING = "data model sketch"
FEATURES_HEADING = "features"
INPUTS_HEADING = "inputs"
DECISIONS_HEADING = "decision log"
OPEN_ITEMS_HEADING = "open items"

DECISION_TAGS = {"stated", "recommended", "open"}
# The artifact types infrahub-speckit's route-specify routes to. The brief's
# Artifacts column is the hook's input, so this is the hook contract, not a
# copy of the skill's prose.
ARTIFACT_TYPES = {"schema", "objects", "generator", "check", "transform", "menu"}
BASIS_STRENGTHS = ("(strong)", "(medium)", "(weak basis)")
# Cell values that stand in for an answer without being one. An unknown
# value has to become an `open: O<n>` reference to a real open item.
PLACEHOLDERS = {"", "-", "--", "?", "tbd", "tba", "todo", "unknown", "n/a",
                "na", "none", "open", "pending"}

_H2 = re.compile(r"^##\s+(.+?)\s*#*\s*$")
_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
_QUESTION = re.compile(r"^\s*\*\*Q(\d+)\s*\(([^)]+)\):\*\*\s*(.*?)\s*$")
_OPTION = re.compile(r"^\s*[-*]\s+([A-Z])\.\s+(.+?)\s*$")
_BASIS = re.compile(r"^\s*\*\*Basis:\*\*\s*(.*?)\s*$")
_RECOMMENDED = re.compile(r"\*\*\(Recommended\)\*\*")
_SENTENCE_QUESTION = re.compile(r"\?(?=[\s*_)\"'”]|$)")
_FEATURE_ID = re.compile(r"\bF(\d+)\b")
_OPEN_REF = re.compile(r"\bopen:\s*(O\d+)\b", re.IGNORECASE)
_OPEN_ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)])?\s*\**\s*(O\d+)\s*\**\s*:", re.IGNORECASE)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
# A top-level schema key on its own line, whether or not the YAML parses.
_SCHEMA_KEY_LINE = re.compile(r"^(nodes|generics):\s*$")
_FILE_REF = re.compile(r"[\w.\-/]*\w\.[A-Za-z0-9]+")


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------


def _fence_marks(text: str) -> list[tuple[str, str]]:
    """Label every line as 'edge', 'inside' or 'outside' a fenced block.

    A fence may be indented (under a list item) and closes only on a run of
    the same character at least as long as the one that opened it, so a
    ``` line inside a ```` block is content, not a close.
    """
    marks: list[tuple[str, str]] = []
    opener: str | None = None
    for line in text.splitlines():
        match = _FENCE_OPEN.match(line)
        if opener is None:
            if match:
                opener = match.group(1)
                marks.append(("edge", line))
            else:
                marks.append(("outside", line))
            continue
        run = match.group(1) if match else ""
        closes = (
            run[:1] == opener[0]
            and len(run) >= len(opener)
            and not line.strip()[len(run):].strip()
        )
        marks.append(("edge" if closes else "inside", line))
        if closes:
            opener = None
    return marks


def _lines_outside_fences(text: str) -> list[str]:
    """Every line that is not inside a fenced code block."""
    return [line for kind, line in _fence_marks(text) if kind == "outside"]


def fenced_blocks(text: str) -> list[str]:
    """Every fenced block, not only the first; an unclosed one counts too."""
    blocks: list[str] = []
    current: list[str] | None = None
    for kind, line in _fence_marks(text):
        if kind == "edge":
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif kind == "inside" and current is not None:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def sections(text: str) -> dict[str, str]:
    """Map each `##` heading (lowercased) to its body, ignoring fenced headings."""
    parts: dict[str, str] = {}
    current: str | None = None
    for kind, line in _fence_marks(text):
        match = _H2.match(line) if kind == "outside" else None
        if match:
            current = _clean(match.group(1)).lower()
            parts[current] = ""
        elif current is not None:
            parts[current] += line + "\n"
    return parts


def _clean(cell: str) -> str:
    """Strip markdown emphasis and code marks from a table cell."""
    cell = cell.strip()
    cell = re.sub(r"[`*]", "", cell)
    cell = re.sub(r"^_+|_+$", "", cell)
    return re.sub(r"\s+", " ", cell).strip()


def _split_row(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip().replace("\\|", "|") for c in _UNESCAPED_PIPE.split(body)]


def first_table(section: str) -> tuple[list[str], list[dict[str, str]]]:
    """The first markdown table in a section: (headers, rows keyed by header).

    Headers are lowercased and cleaned; raw cell text is kept so callers can
    decide how to clean it.
    """
    lines = _lines_outside_fences(section)
    for i in range(len(lines) - 1):
        if "|" in lines[i] and _TABLE_SEP.match(lines[i + 1]):
            headers = [_clean(h).lower() for h in _split_row(lines[i])]
            rows: list[dict[str, str]] = []
            for line in lines[i + 2:]:
                if "|" not in line or not line.strip():
                    break
                cells = _split_row(line)
                cells += [""] * (len(headers) - len(cells))
                rows.append(dict(zip(headers, cells)))
            return headers, rows
    return [], []


def _column(headers: list[str], name: str) -> str | None:
    """Find a column by exact name, or by prefix for annotated headers."""
    for header in headers:
        if header == name:
            return header
    for header in headers:
        if header.startswith(name + " ") or header.startswith(name + "("):
            return header
    return None


def find_brief(ws: Path) -> tuple[Path | None, str]:
    found = sorted(p for pattern in BRIEF_GLOBS for p in ws.glob(pattern))
    where = " or ".join(BRIEF_GLOBS)
    if not found:
        return None, f"no brief at {where}"
    if len(found) > 1:
        names = ", ".join(str(p.relative_to(ws)) for p in found)
        return None, f"expected one brief at {where}, found {len(found)}: {names}"
    return found[0], ""


def _brief_sections(ws: Path) -> tuple[dict[str, str] | None, str]:
    brief, err = find_brief(ws)
    if brief is None:
        return None, err
    return sections(brief.read_text()), ""


def _sketch(parts: dict[str, str]) -> tuple[list[str], list[dict[str, str]], str]:
    if SKETCH_HEADING not in parts:
        return [], [], "brief has no '## Data model sketch' section"
    headers, rows = first_table(parts[SKETCH_HEADING])
    if not rows:
        return [], [], "Data model sketch has no table rows"
    return headers, rows, ""


def _open_item_ids(parts: dict[str, str]) -> set[str]:
    body = parts.get(OPEN_ITEMS_HEADING, "")
    ids = set()
    for line in _lines_outside_fences(body):
        match = _OPEN_ITEM.match(line)
        if match:
            ids.add(match.group(1).upper())
    return ids


# --------------------------------------------------------------------------
# Rule: interview-one-question-recommended  (artifact: output_dir/answer.md)
# --------------------------------------------------------------------------


def _schema_yaml_blocks(text: str) -> list[str]:
    """Schema YAML anywhere in the reply, parseable or not.

    A must-not check fails closed: a block that does not parse but carries a
    top-level ``nodes:`` or ``generics:`` line is still a schema draft, and
    so is the same line written outside any fence.
    """
    hits = []
    for block in fenced_blocks(text):
        if any(_SCHEMA_KEY_LINE.match(ln) for ln in block.splitlines()):
            hits.append(block)
            continue
        try:
            docs = list(yaml.safe_load_all(block))
        except yaml.YAMLError:
            continue
        if any(isinstance(d, dict) and {"nodes", "generics"} & set(d) for d in docs):
            hits.append(block)
    hits += [ln for ln in _lines_outside_fences(text) if _SCHEMA_KEY_LINE.match(ln)]
    return hits


def check_one_question_recommended(ws: Path) -> tuple[bool, str]:
    """The reply is exactly one question block with one recommended option."""
    path = ws / ANSWER_PATH
    if not path.is_file():
        return False, f"no {ANSWER_PATH}"
    text = path.read_text()

    if _schema_yaml_blocks(text):
        return False, "reply contains schema YAML (a fenced block with nodes: or generics:)"

    lines = _lines_outside_fences(text)
    q_idx = [i for i, ln in enumerate(lines) if _QUESTION.match(ln)]
    if len(q_idx) != 1:
        return False, f"expected exactly one '**Q<n> (<layer>):**' line, found {len(q_idx)}"
    q_line = _QUESTION.match(lines[q_idx[0]])
    if not q_line.group(3).rstrip().endswith("?"):
        return False, "the question line does not end with '?'"

    options = [i for i, ln in enumerate(lines) if _OPTION.match(ln)]
    if not 2 <= len(options) <= 4:
        return False, f"expected 2-4 option lines '- A. ...', found {len(options)}"
    if any(i < q_idx[0] for i in options):
        return False, "an option line appears before the question line"

    recommended_lines = [i for i, ln in enumerate(lines) if _RECOMMENDED.search(ln)]
    recommended_count = sum(len(_RECOMMENDED.findall(lines[i])) for i in recommended_lines)
    if recommended_count != 1:
        return False, f"expected exactly one '**(Recommended)**' tag, found {recommended_count}"
    if recommended_lines[0] not in options:
        return False, "the '**(Recommended)**' tag is not on an option line"

    basis_idx = [i for i, ln in enumerate(lines) if _BASIS.match(ln)]
    if len(basis_idx) != 1:
        return False, f"expected exactly one '**Basis:**' line, found {len(basis_idx)}"
    start = basis_idx[0]
    basis_parts = [_BASIS.match(lines[start]).group(1)]
    end = start + 1
    while end < len(lines) and lines[end].strip():
        basis_parts.append(lines[end].strip())
        end += 1
    basis = " ".join(p for p in basis_parts if p).strip().rstrip(".").strip()
    if not basis:
        return False, "the '**Basis:**' line is empty"
    if not basis.lower().endswith(BASIS_STRENGTHS):
        return False, "the Basis does not end with (strong), (medium) or (weak basis)"
    if start < max(options):
        return False, "the '**Basis:**' line comes before the last option"

    basis_lines = set(range(start, end))
    for i, line in enumerate(lines):
        if i == q_idx[0] or i in options or i in basis_lines:
            continue
        if _SENTENCE_QUESTION.search(line):
            return False, f"a second question outside the block: {line.strip()[:80]!r}"
    return True, "one question block, one recommended option with a basis, no schema YAML"


# --------------------------------------------------------------------------
# Rule: interview-inputs-digested  (artifact: the brief)
# --------------------------------------------------------------------------


def _file_names(cell: str) -> set[str]:
    """Base names of the files a cell names, e.g. '`inputs/pops.csv:pop_code`' -> {'pops.csv'}.

    Compared whole, so ``old_pops.csv`` does not count as ``pops.csv``.
    """
    return {Path(m).name.lower() for m in _FILE_REF.findall(_clean(cell))}


def check_inputs_digested(ws: Path, inputs: dict[str, list[str]]) -> tuple[bool, str]:
    """Every input file is listed and used as evidence for the sketch.

    ``inputs`` maps each file the task provided to its CSV column headers
    (empty for files that are not tables). A sketch row identified by one of
    a file's columns must name that file in its Evidence cell, and every
    file must be the evidence for at least one row.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if INPUTS_HEADING not in parts:
        return False, "brief has no '## Inputs' section"
    in_headers, in_rows = first_table(parts[INPUTS_HEADING])
    file_col = _column(in_headers, "file")
    taken_col = _column(in_headers, "taken from it")
    if not in_rows or file_col is None or taken_col is None:
        return False, "Inputs section has no '| File | Taken from it |' table"
    listed = {}
    for r in in_rows:
        for name in _file_names(r[file_col]):
            listed[name] = _clean(r[taken_col])
    for name in inputs:
        if name.lower() not in listed:
            return False, f"Inputs table does not list {name}"
        if listed[name.lower()].lower() in PLACEHOLDERS:
            return False, f"Inputs row for {name} says nothing about what was taken"

    headers, rows, err = _sketch(parts)
    if err:
        return False, err
    ev_col = _column(headers, "evidence")
    id_col = _column(headers, "identified by")
    if ev_col is None or id_col is None:
        return False, "sketch table lacks an 'Identified by' or 'Evidence' column"

    cited: set[str] = set()
    for row in rows:
        named = _file_names(row.get(ev_col, ""))
        cited_here = {n for n in inputs if n.lower() in named}
        cited |= cited_here
        identity_tokens = set(re.findall(r"[a-z0-9_]+", _clean(row.get(id_col, "")).lower()))
        for name, columns in inputs.items():
            if identity_tokens & {c.lower() for c in columns} and name not in cited_here:
                kind = _clean(row.get(_column(headers, "node kind") or "", ""))
                return False, (
                    f"sketch row {kind or '?'} is identified by a {name} column "
                    f"but its Evidence does not name {name}"
                )
    for name in inputs:
        if name not in cited:
            return False, f"no sketch row cites {name} as evidence"
    return True, "every input listed and cited as evidence"


# --------------------------------------------------------------------------
# Rule: scope-split-before-data-layer  (artifact: the brief)
# --------------------------------------------------------------------------


def check_scope_split_f1_only(ws: Path) -> tuple[bool, str]:
    """A split brief orders features by dependency and sketches F1 only."""
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if FEATURES_HEADING not in parts:
        return False, "brief has no '## Features' section although the scope needs a split"
    headers, rows = first_table(parts[FEATURES_HEADING])
    id_col = _column(headers, "id")
    dep_col = _column(headers, "depends on")
    if not rows or id_col is None or dep_col is None:
        return False, "Features section has no table with 'ID' and 'Depends on' columns"
    if len(rows) < 2:
        return False, f"Features table has {len(rows)} row; a split needs at least 2"

    for position, row in enumerate(rows, start=1):
        ids = _FEATURE_ID.findall(_clean(row[id_col]))
        if ids != [str(position)]:
            return False, f"Features row {position} has ID {_clean(row[id_col])!r}, expected F{position}"
        deps = [int(d) for d in _FEATURE_ID.findall(_clean(row[dep_col]))]
        if position > 1 and not deps:
            return False, f"F{position} has an empty 'Depends on'"
        if any(d >= position for d in deps):
            return False, f"F{position} depends on a later or same feature: {deps}"

    s_headers, s_rows, err = _sketch(parts)
    if err:
        return False, err
    feat_col = _column(s_headers, "feature")
    if feat_col is None:
        return False, "sketch table has no 'Feature' column"
    for row in s_rows:
        ids = _FEATURE_ID.findall(_clean(row[feat_col]))
        if ids != ["1"]:
            return False, f"sketch has a row for {_clean(row[feat_col])!r}; only F1 is modelled in depth"
    return True, f"{len(rows)} features in dependency order, sketch covers F1 only"


def check_features_artifacts(ws: Path) -> tuple[bool, str]:
    """Every feature lists the artifacts to specify, in routable order.

    The Features table is present even for a single feature, so the hook
    reads one shape. Each Artifacts cell is an ordered list of artifact
    types, with schema first whenever it appears, because every other
    artifact reads the schema.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if FEATURES_HEADING not in parts:
        return False, "brief has no '## Features' section (required even for one feature)"
    headers, rows = first_table(parts[FEATURES_HEADING])
    art_col = _column(headers, "artifacts")
    id_col = _column(headers, "id")
    if not rows or art_col is None or id_col is None:
        return False, "Features table has no 'ID' and 'Artifacts' columns"
    for row in rows:
        fid = _clean(row[id_col]) or "?"
        items = [a for a in re.split(r"[,;]|\band\b|->|→", _clean(row[art_col]).lower()) if a.strip()]
        items = [a.strip() for a in items]
        if not items:
            return False, f"{fid} has an empty Artifacts cell"
        unknown = [a for a in items if a not in ARTIFACT_TYPES]
        if unknown:
            return False, f"{fid} lists {unknown}, which are not artifact types the hook can route"
        if "schema" in items and items[0] != "schema":
            return False, f"{fid} lists {items}; schema must come first"
    return True, "every feature lists routable artifacts, schema first"


# --------------------------------------------------------------------------
# Rule: brief-sketch-rows-complete  (artifact: the brief)
# --------------------------------------------------------------------------

_REQUIRED_SKETCH_COLUMNS = ("identified by", "source of truth", "owner")


def check_sketch_rows_complete(ws: Path) -> tuple[bool, str]:
    """Identity, source of truth and owner are answered or reference an open item."""
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    headers, rows, err = _sketch(parts)
    if err:
        return False, err
    columns = {}
    for name in _REQUIRED_SKETCH_COLUMNS:
        col = _column(headers, name)
        if col is None:
            return False, f"sketch table has no '{name}' column"
        columns[name] = col
    open_ids = _open_item_ids(parts)
    kind_col = _column(headers, "node kind") or ""
    for row in rows:
        kind = _clean(row.get(kind_col, "")) or "?"
        for name, col in columns.items():
            value = _clean(row.get(col, ""))
            ref = _OPEN_REF.search(value)
            if ref:
                if ref.group(1).upper() not in open_ids:
                    return False, f"{kind}: {name} references {ref.group(1)}, which is not in Open items"
                continue
            if value.lower().rstrip(".") in PLACEHOLDERS:
                return False, f"{kind}: {name} is {value!r}, neither an answer nor an open item reference"
    return True, "every sketch row has identity, source of truth and owner, or an open item"


def check_open_item_for(ws: Path, kind: re.Pattern, column: str) -> tuple[bool, str]:
    """The value the user left unknown is an open item on its own row.

    Bound to the subject: a brief that invents the unknown value and parks an
    open item on some other row still fails. ``kind`` matches the node kind
    the task left unknown; ``column`` names the sketch column.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    headers, rows, err = _sketch(parts)
    if err:
        return False, err
    kind_col = _column(headers, "node kind")
    value_col = _column(headers, column)
    if kind_col is None or value_col is None:
        return False, f"sketch table lacks a 'Node kind' or '{column}' column"
    subject = [r for r in rows if kind.search(_clean(r[kind_col]))]
    if not subject:
        return False, f"no sketch row for the node kind matching {kind.pattern!r}"
    open_ids = _open_item_ids(parts)
    for row in subject:
        value = _clean(row[value_col])
        ref = _OPEN_REF.search(value)
        if not ref or ref.group(1).upper() not in open_ids:
            return False, (
                f"{_clean(row[kind_col])}: {column} is {value!r}; the user did not "
                "know it, so it must reference an open item"
            )
    return True, f"the unknown {column} is deferred to an open item"


# --------------------------------------------------------------------------
# Rule: brief-decision-provenance  (artifact: the brief)
# --------------------------------------------------------------------------


def _decision_rows(parts: dict[str, str]) -> tuple[list[dict[str, str]], str, str, str]:
    if DECISIONS_HEADING not in parts:
        return [], "", "", "brief has no '## Decision log' section"
    headers, rows = first_table(parts[DECISIONS_HEADING])
    tag_col = _column(headers, "tag")
    basis_col = _column(headers, "basis")
    if not rows or tag_col is None or basis_col is None:
        return [], "", "", "Decision log has no table with 'Tag' and 'Basis' columns"
    return rows, tag_col, basis_col, ""


def check_decision_provenance(ws: Path) -> tuple[bool, str]:
    """Every decision is tagged stated, recommended or open; recommended ones carry a basis."""
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    rows, tag_col, basis_col, err = _decision_rows(parts)
    if err:
        return False, err
    for number, row in enumerate(rows, start=1):
        tag = _clean(row[tag_col]).lower()
        if tag not in DECISION_TAGS:
            return False, f"decision {number} has tag {tag!r}; expected stated, recommended or open"
        if tag == "recommended" and _clean(row[basis_col]).lower() in PLACEHOLDERS:
            return False, f"decision {number} is recommended but has no basis"
    return True, f"{len(rows)} decisions, each tagged with its provenance"


def check_decision_tags_for(ws: Path, subjects: dict[str, tuple[re.Pattern, str]]) -> tuple[bool, str]:
    """Each named decision carries the tag the transcript gives it.

    Bound to the subject: swapping tags between a stated decision and an
    accepted recommendation fails, although both tags still appear.
    ``subjects`` maps a label to (pattern on the Decision cell, expected tag).
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    rows, tag_col, _, err = _decision_rows(parts)
    if err:
        return False, err
    headers, _ = first_table(parts[DECISIONS_HEADING])
    dec_col = _column(headers, "decision")
    if dec_col is None:
        return False, "Decision log has no 'Decision' column"
    for label, (pattern, tag) in subjects.items():
        matching = [r for r in rows if pattern.search(_clean(r[dec_col]))]
        if not matching:
            return False, f"no decision about {label}"
        wrong = [_clean(r[tag_col]).lower() for r in matching if _clean(r[tag_col]).lower() != tag]
        if wrong:
            return False, f"the decision about {label} is tagged {wrong[0]!r}; the transcript makes it {tag!r}"
    return True, "each decision carries the provenance the transcript gives it"


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

CHECKS: dict[str, Callable[[Path], tuple[bool, str]]] = {
    "one-question-recommended": check_one_question_recommended,
    "scope-split-f1-only": check_scope_split_f1_only,
    "features-artifacts": check_features_artifacts,
    "sketch-rows-complete": check_sketch_rows_complete,
    "decision-provenance": check_decision_provenance,
}


def run_checks(
    names: list[str],
    workspace: Path,
    extra: dict[str, Callable[[Path], tuple[bool, str]]] | None = None,
) -> dict:
    """Run named checks and return skillgrade JSON.

    ``extra`` supplies checks bound to a task's own inputs (for example the
    files a task provided), which have no place in the shared registry.
    """
    registry = {**CHECKS, **(extra or {})}
    results = []
    for name in names:
        fn = registry.get(name)
        if fn is None:
            results.append({"name": name, "passed": False, "message": "unknown check"})
            continue
        try:
            passed, message = fn(workspace)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed check
            passed, message = False, f"check crashed: {exc}"
        results.append({"name": name, "passed": passed, "message": message})
    score = sum(r["passed"] for r in results) / len(results) if results else 0.0
    failures = "; ".join(f"{r['name']}: {r['message']}" for r in results if not r["passed"])
    return {
        "score": round(score, 2),
        "details": failures or "all checks passed",
        "checks": results,
    }
