#!/usr/bin/env python3
"""Shared grader library for infrahub-designing-models skill evaluations.

Two artifacts are graded:

- ``output_dir/answer.md``: the next message of an interview, which must be
  exactly one question block (rule interview-one-question-recommended).
- ``design-brief.md``: the design brief the skill writes at the end of a
  session, in an existing design-document location or under
  ``docs/designs/<design-slug>/`` by default (rules
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
# These cover the default and the established location used by existing
# fixtures; a session writes exactly one brief.
BRIEF_GLOBS = ("specs/*/design-brief.md", "docs/designs/*/design-brief.md")

SKETCH_HEADING = "data model sketch"
FEATURES_HEADING = "features"
INPUTS_HEADING = "inputs"
DECISIONS_HEADING = "decision log"
OPEN_ITEMS_HEADING = "open items"

DECISION_TAGS = {"stated", "recommended", "open"}
# The artifact types the downstream Infrahub skills can produce. The brief's
# Artifacts column is their routing input, so this is the integration contract,
# not a copy of the skill's prose.
ARTIFACT_TYPES = {"schema", "objects", "generator", "check", "transform", "menu"}
BASIS_STRENGTHS = ("(strong)", "(medium)", "(weak basis)")
# Mirrors the layers named in rules/interview-one-question-recommended.md.
QUESTION_LAYERS = {"inputs", "business", "service", "scope", "data"}
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
_NO_PREREQUISITE = {"-", "none"}
_OPEN_REF = re.compile(r"\bopen:\s*(O\d+)\b", re.IGNORECASE)
_OPEN_ID = re.compile(r"\b(O\d+)\b", re.IGNORECASE)
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
    layer = q_line.group(2).strip().lower()
    if layer not in QUESTION_LAYERS:
        return False, f"question layer {layer!r} is not one of inputs, business, service, scope, data"
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
        return False, f"the Basis does not end with (strong), (medium) or (weak basis): {basis[-80:]!r}"
    if start < max(options):
        return False, "the '**Basis:**' line comes before the last option"

    # The Basis paragraph is scanned too: a question in the rationale is
    # still a second question.
    for i, line in enumerate(lines):
        if i == q_idx[0] or i in options:
            continue
        if _SENTENCE_QUESTION.search(line):
            return False, f"a second question outside the block: {line.strip()[:80]!r}"

    # The Basis paragraph ends the message. Walk the raw lines, fences
    # included, so content hidden in a fenced block after it fails too.
    marks = _fence_marks(text)
    raw_start = [i for i, (kind, _) in enumerate(marks) if kind == "outside"][start]
    raw_end = raw_start + 1
    while raw_end < len(marks) and marks[raw_end][0] == "outside" and marks[raw_end][1].strip():
        raw_end += 1
    tail = [line.strip() for _, line in marks[raw_end:] if line.strip()]
    if tail:
        return False, f"content after the **Basis:** line, which must end the message: {tail[0][:60]!r}"
    return True, "one question block, one recommended option with a basis, no schema YAML"


# --------------------------------------------------------------------------
# Rule: interview-inputs-digested  (artifact: the brief)
# --------------------------------------------------------------------------


def _file_names(cell: str) -> set[str]:
    """Base names of the files a cell names, e.g. '`inputs/pops.csv:pop_code`' -> {'pops.csv'}.

    Compared whole, so ``old_pops.csv`` does not count as ``pops.csv``.
    """
    return {Path(m).name.lower() for m in _FILE_REF.findall(_clean(cell))}


_LOCATOR = re.compile(r"^(?::\s*[^\s:]|\s*\(\s*[^)\s][^)]*\))")


def _citations(cell: str) -> list[str]:
    """Split an Evidence cell into its citations on ';' and ',' outside parentheses.

    ``pops.csv (pop_code, region columns); backbone.txt:links`` gives two
    citations, not three.
    """
    out, depth, current = [], 0, ""
    for ch in _clean(cell):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        if ch in ";," and depth == 0:
            out.append(current.strip())
            current = ""
            continue
        current += ch
    out.append(current.strip())
    return [c for c in out if c]


def _cited_files(cell: str, inputs: dict[str, list[str]]) -> tuple[set[str], set[str]]:
    """Input files a cell cites, and those cited without a locator.

    A locator follows the file name as ``file:column`` / ``file:element`` or
    ``file (column)`` / ``file (element)``.
    """
    wanted = {n.lower(): n for n in inputs}
    cited: set[str] = set()
    bare: set[str] = set()
    for citation in _citations(cell):
        for match in _FILE_REF.finditer(citation):
            name = wanted.get(Path(match.group(0)).name.lower())
            if name is None:
                continue
            cited.add(name)
            if not _LOCATOR.match(citation[match.end():]):
                bare.add(name)
    return cited, bare


def check_inputs_digested(
    ws: Path,
    inputs: dict[str, list[str]],
    sources: dict[str, re.Pattern] | None = None,
) -> tuple[bool, str]:
    """Every input file is listed and used as evidence for the sketch.

    ``inputs`` maps each file the task provided to its CSV column headers
    (empty for files that are not tables). A sketch row identified by one of
    a file's columns must cite that file in its Evidence cell, every citation
    of an input file carries a locator, and every file must be the evidence
    for at least one row.

    ``sources`` optionally binds a file to the sketch rows whose facts the
    task put in it: every row whose Node kind matches the file's pattern must
    cite that file, and at least one row must match, so a brief cannot pass
    by leaving those rows out.
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
    kind_col = _column(headers, "node kind") or ""
    if ev_col is None or id_col is None:
        return False, "sketch table lacks an 'Identified by' or 'Evidence' column"

    sources = sources or {}
    matched: set[str] = set()
    cited: set[str] = set()
    for row in rows:
        kind = _clean(row.get(kind_col, "")) or "?"
        cited_here, bare = _cited_files(row.get(ev_col, ""), inputs)
        cited |= cited_here
        identity_tokens = set(re.findall(r"[a-z0-9_]+", _clean(row.get(id_col, "")).lower()))
        for name, columns in inputs.items():
            if identity_tokens & {c.lower() for c in columns} and name not in cited_here:
                return False, (
                    f"sketch row {kind} is identified by a {name} column "
                    f"but its Evidence does not name {name}"
                )
        for name in sorted(bare):
            return False, f"Evidence for {kind} cites {name} without a locator (file:column or file:element)"
        for name, pattern in sources.items():
            if pattern.search(kind):
                matched.add(name)
                if name not in cited_here:
                    return False, f"{kind} is a {name} fact but its Evidence does not cite {name}"
    for name in inputs:
        if name not in cited:
            return False, f"no sketch row cites {name} as evidence"
    for name, pattern in sources.items():
        if name not in matched:
            return False, f"no sketch row has a node kind matching {pattern.pattern!r}, the facts {name} holds"
    return True, "every input listed, and each fact cites its own file with a locator"


# --------------------------------------------------------------------------
# Rule: scope-split-before-data-layer  (artifact: the brief)
# --------------------------------------------------------------------------


def check_scope_split_f1_only(ws: Path) -> tuple[bool, str]:
    """A split brief orders features, hands each off, and sketches F1 only."""
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if FEATURES_HEADING not in parts:
        return False, "brief has no '## Features' section although the scope needs a split"
    headers, rows = first_table(parts[FEATURES_HEADING])
    id_col = _column(headers, "id")
    dep_col = _column(headers, "depends on")
    handoff_col = _column(headers, "handoff")
    if not rows or id_col is None or dep_col is None or handoff_col is None:
        return False, "Features section has no table with 'ID', 'Depends on', and 'Handoff' columns"
    if len(rows) < 2:
        return False, f"Features table has {len(rows)} row; a split needs at least 2"

    for position, row in enumerate(rows, start=1):
        ids = _FEATURE_ID.findall(_clean(row[id_col]))
        if ids != [str(position)]:
            return False, f"Features row {position} has ID {_clean(row[id_col])!r}, expected F{position}"
        dep_cell = _clean(row[dep_col])
        if not dep_cell:
            return False, f"F{position} has an empty 'Depends on'; write - when it has no prerequisite"
        if dep_cell.lower() not in _NO_PREREQUISITE:
            deps = [int(d) for d in _FEATURE_ID.findall(dep_cell)]
            if not deps:
                return False, f"F{position} 'Depends on' is {dep_cell!r}; name earlier IDs, or write - for none"
            for d in deps:
                if d < 1 or d >= position:
                    return False, f"F{position} depends on F{d}, which is not an earlier feature"
        if not _clean(row[handoff_col]):
            return False, f"F{position} has an empty Handoff cell"

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
    return True, f"{len(rows)} features have handoffs in dependency order, sketch covers F1 only"


def check_features_artifacts(ws: Path) -> tuple[bool, str]:
    """Every feature lists supported implementation artifacts in build order.

    The Features table is present even for a single feature, so downstream
    workflows read one shape. Each Artifacts cell is an ordered list of
    artifact types, with schema first whenever it appears, because every
    other artifact reads the schema.
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
            return False, f"{fid} lists {unknown}, which are not supported artifact types"
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
    """Every decision is tagged stated, recommended or open.

    A recommended row carries a basis; an open row names its open item
    (``O<n>``) in Basis, and that item is listed under Open items.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    rows, tag_col, basis_col, err = _decision_rows(parts)
    if err:
        return False, err
    open_ids = _open_item_ids(parts)
    for number, row in enumerate(rows, start=1):
        tag = _clean(row[tag_col]).lower()
        if tag not in DECISION_TAGS:
            return False, f"decision {number} has tag {tag!r}; expected stated, recommended or open"
        basis = _clean(row[basis_col])
        if tag == "recommended" and basis.lower() in PLACEHOLDERS:
            return False, f"decision {number} is recommended but has no basis"
        if tag == "open":
            ref = _OPEN_ID.search(basis)
            if not ref:
                return False, f"decision {number} is open but its Basis names no open item (O<n>)"
            if ref.group(1).upper() not in open_ids:
                return False, f"decision {number} is open but {ref.group(1).upper()} is not in Open items"
    return True, f"{len(rows)} decisions, each tagged with its provenance"


def check_decision_tags_for(ws: Path, subjects: dict[str, tuple[re.Pattern, str]]) -> tuple[bool, str]:
    """Each named decision carries the tag the transcript gives it.

    Bound to the subject: swapping tags between a stated decision and an
    accepted recommendation fails, although both tags still appear. A related
    `open` row (a follow-up question about the same subject) is allowed, as
    the rule allows open decisions; at least one row must carry the expected
    tag and none the swapped one. ``subjects`` maps a label to (pattern on
    the Decision cell, expected tag).
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
        tags = {_clean(r[tag_col]).lower() for r in matching}
        swapped = (tags - {tag, "open"})
        if swapped or tag not in tags:
            found = sorted(swapped) or sorted(tags)
            return False, f"the decision about {label} is tagged {found[0]!r}; the transcript makes it {tag!r}"
    return True, "each decision carries the provenance the transcript gives it"


# --------------------------------------------------------------------------
# Rule: brief-maps-match-tables  (artifact: the brief)
# --------------------------------------------------------------------------

# Arrows and lines a flowchart can draw between two nodes, with an optional
# |label|. Direction is read from the order of the two endpoints.
_ARROW = re.compile(r"\s*(?:-{2,3}>|-{3}|={2,3}>|-\.+->|-\.+-)(?:\|[^|]*\|)?\s*")
_NODE_DEF = re.compile(r'([A-Za-z_][\w-]*)\s*\[\s*"(.*?)"\s*\]|([A-Za-z_][\w-]*)\s*\[([^\]"]*)\]', re.S)
_KIND = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _mermaid_blocks(section: str) -> list[str]:
    """Every fenced block in a section whose opener names mermaid."""
    blocks: list[str] = []
    current: list[str] | None = None
    is_mermaid = False
    for kind, line in _fence_marks(section):
        if kind == "edge":
            if current is None:
                current = []
                is_mermaid = line.strip().lstrip("`~").strip().lower().startswith("mermaid")
            else:
                if is_mermaid:
                    blocks.append("\n".join(current))
                current = None
        elif kind == "inside" and current is not None:
            current.append(line)
    if current is not None and is_mermaid:
        blocks.append("\n".join(current))
    return blocks


def parse_flowchart(block: str) -> tuple[dict[str, str], set[tuple[str, str]], str]:
    """Nodes (id -> label) and directed edges of a Mermaid flowchart.

    Labels may span lines inside quotes. Returns an error string, never a
    partial graph, when the block is not a flowchart this parser reads, so
    a check built on it fails closed.
    """
    lines = [ln for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("%%")]
    if not lines or not re.match(r"^\s*(graph|flowchart)\b", lines[0]):
        return {}, set(), "the map is not a Mermaid graph or flowchart"
    body = "\n".join(lines[1:])
    nodes: dict[str, str] = {}

    def keep(match: re.Match) -> str:
        node_id = match.group(1) or match.group(3)
        label = match.group(2) if match.group(1) else match.group(4)
        nodes[node_id] = re.sub(r"\s+", " ", label).strip()
        return node_id

    body = _NODE_DEF.sub(keep, body)
    edges: set[tuple[str, str]] = set()
    for line in body.splitlines():
        line = re.sub(r":::\w+", "", line).strip()
        if not line or re.match(r"^(classDef|class|style|linkStyle|subgraph|end|direction)\b", line):
            continue
        parts = [x.strip() for x in _ARROW.split(line)]
        if len(parts) == 1:
            if not re.fullmatch(r"[A-Za-z_][\w-]*", parts[0]):
                return {}, set(), f"the map has a line it cannot read: {line[:60]!r}"
            nodes.setdefault(parts[0], parts[0])
            continue
        if not all(re.fullmatch(r"[A-Za-z_][\w-]*", x) for x in parts):
            return {}, set(), f"the map has a line it cannot read: {line[:60]!r}"
        for a, b in zip(parts, parts[1:]):
            nodes.setdefault(a, a)
            nodes.setdefault(b, b)
            edges.add((a, b))
    return nodes, edges, ""


def _one_map(parts: dict[str, str], heading: str, what: str) -> tuple[dict[str, str], set[tuple[str, str]], str]:
    blocks = _mermaid_blocks(parts.get(heading, ""))
    if len(blocks) != 1:
        return {}, set(), f"the {what} section needs exactly one mermaid map, found {len(blocks)}"
    return parse_flowchart(blocks[0])


def check_plan_map_matches(ws: Path) -> tuple[bool, str]:
    """The Features map shows each feature with its artifacts and each dependency.

    The table is the source; the map must agree with it exactly: one node per
    feature, labelled with its ID and its artifacts, and one arrow from each
    feature it depends on.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    headers, rows = first_table(parts.get(FEATURES_HEADING, ""))
    id_col = _column(headers, "id")
    art_col = _column(headers, "artifacts")
    dep_col = _column(headers, "depends on")
    if not rows or None in (id_col, art_col, dep_col):
        return False, "Features table has no 'ID', 'Artifacts' and 'Depends on' columns"
    nodes, edges, err = _one_map(parts, FEATURES_HEADING, "Features")
    if err:
        return False, f"plan map: {err}"

    by_feature: dict[str, str] = {}
    for node_id, label in nodes.items():
        ids = _FEATURE_ID.findall(label) or _FEATURE_ID.findall(node_id)
        if len(ids) != 1:
            return False, f"plan map node {node_id!r} names {len(ids)} feature IDs, expected one"
        fid = f"F{ids[0]}"
        if fid in by_feature:
            return False, f"plan map shows {fid} twice"
        by_feature[fid] = node_id

    table_ids = []
    want_edges: set[tuple[str, str]] = set()
    for row in rows:
        fid = "F" + _FEATURE_ID.findall(_clean(row[id_col]))[0] if _FEATURE_ID.findall(_clean(row[id_col])) else "?"
        table_ids.append(fid)
        for dep in _FEATURE_ID.findall(_clean(row[dep_col])):
            want_edges.add((f"F{dep}", fid))
        if fid in by_feature:
            label_words = set(re.findall(r"[a-z]+", nodes[by_feature[fid]].lower()))
            want = {a.strip() for a in re.split(r"[,;]|\band\b|->|→", _clean(row[art_col]).lower()) if a.strip()}
            missing = sorted(want - label_words)
            if missing:
                return False, f"plan map node for {fid} does not show its artifacts {missing}"
    if sorted(by_feature) != sorted(table_ids):
        return False, f"plan map shows {sorted(by_feature)}, the Features table has {sorted(table_ids)}"

    to_fid = {v: k for k, v in by_feature.items()}
    got_edges = {(to_fid[a], to_fid[b]) for a, b in edges}
    if got_edges != want_edges:
        extra = sorted(got_edges - want_edges)
        missing = sorted(want_edges - got_edges)
        return False, f"plan map arrows differ from 'Depends on': missing {missing}, extra {extra}"
    return True, "plan map matches the Features table"


def _peer_kinds(cell: str) -> set[str]:
    """Node kinds named in a Peers cell such as 'Rack (many), Site (one)'."""
    kinds = set()
    for item in re.split(r"[,;]", _clean(cell)):
        match = _KIND.match(item.strip())
        if match and match.group(0).lower() not in PLACEHOLDERS:
            kinds.add(match.group(0))
    return kinds


def check_model_map_matches(ws: Path) -> tuple[bool, str]:
    """The sketch map shows each node kind and one line per peer in the table.

    The table is the source. Each sketch row is a node; each kind in its
    Peers cell is a line between the two, in either direction. A line the
    table does not have, or a peer with no line, fails. So does a node whose
    kind is neither a sketch row nor a peer, and a kind drawn twice.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    headers, rows, err = _sketch(parts)
    if err:
        return False, err
    kind_col = _column(headers, "node kind")
    peer_col = _column(headers, "peers")
    if kind_col is None or peer_col is None:
        return False, "sketch table lacks a 'Node kind' or 'Peers' column"
    nodes, edges, err = _one_map(parts, SKETCH_HEADING, "Data model sketch")
    if err:
        return False, f"model map: {err}"

    def kind_of(node_id: str) -> str:
        match = _KIND.match(nodes[node_id])
        return match.group(0) if match else node_id

    shown: set[str] = set()
    for node_id in nodes:
        kind = kind_of(node_id)
        if kind in shown:
            return False, f"model map draws {kind} twice"
        shown.add(kind)
    want: set[frozenset] = set()
    allowed: set[str] = set()
    for row in rows:
        kind = _KIND.match(_clean(row[kind_col]))
        if not kind:
            continue
        kind = kind.group(0)
        allowed.add(kind)
        if kind not in shown:
            return False, f"model map has no node for {kind}"
        for peer in _peer_kinds(row[peer_col]):
            allowed.add(peer)
            want.add(frozenset((kind, peer)))
    unknown = sorted(shown - allowed)
    if unknown:
        return False, f"model map shows {unknown[0]}, which is not in the sketch table"
    got = {frozenset((kind_of(a), kind_of(b))) for a, b in edges}
    missing = sorted(tuple(sorted(e)) for e in want - got)
    extra = sorted(tuple(sorted(e)) for e in got - want)
    if missing or extra:
        return False, f"model map lines differ from the Peers column: missing {missing}, extra {extra}"
    return True, "model map matches the sketch table"


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

CHECKS: dict[str, Callable[[Path], tuple[bool, str]]] = {
    "one-question-recommended": check_one_question_recommended,
    "scope-split-f1-only": check_scope_split_f1_only,
    "features-artifacts": check_features_artifacts,
    "plan-map-matches": check_plan_map_matches,
    "model-map-matches": check_model_map_matches,
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
