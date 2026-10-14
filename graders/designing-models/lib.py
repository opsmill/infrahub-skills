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

import fnmatch
import os
import re
from pathlib import Path
from typing import Callable

import yaml

ANSWER_PATH = Path("output_dir") / "answer.md"
# These cover the default and the established location used by existing
# fixtures; a session writes exactly one brief.
# The one location references/brief-format.md gives the brief.
BRIEF_GLOBS = ("docs/designs/*/design-brief.md",)

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
# The draft shown during the interview marks unconfirmed cells "(guess)" and
# unsupported ones "(open)"; neither may reach the brief.
_DRAFT_MARK = re.compile(r"\(\s*(?:guess|open)\s*\)", re.IGNORECASE)
_OPEN_REF = re.compile(r"\bopen:\s*(O\d+)\b", re.IGNORECASE)
_OPEN_ID = re.compile(r"\b(O\d+)\b", re.IGNORECASE)
_OPEN_ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)])?\s*\**\s*(O\d+)\s*\**\s*:(.*)$", re.IGNORECASE)
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


def _artifacts(cell: str) -> list[str]:
    """The artifact types an Artifacts cell lists, lower-cased."""
    return [a.strip() for a in re.split(r"[,;]|\band\b|->|→", _clean(cell).lower()) if a.strip()]


def _is_placeholder(value: str) -> bool:
    return value.lower().rstrip(".") in PLACEHOLDERS


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


# Folders a stray brief is never looked for in: the skills themselves, the
# docs site, and tool folders that can hold thousands of files.
_SKIP_TOP = {"skills", ".agents", ".claude", ".codex"}
_SKIP_ANY = {"node_modules", ".git", ".venv", "__pycache__"}


def _stray_briefs(ws: Path) -> list[str]:
    """Brief-like Markdown files outside the expected paths, pruning skipped folders while walking."""
    found = []
    for root, dirs, files in os.walk(ws):
        rel = Path(root).relative_to(ws)
        dirs[:] = [
            d for d in dirs
            if d not in _SKIP_ANY
            and not (rel == Path(".") and d in _SKIP_TOP)
            and not (rel == Path("docs") and d == "docs")
        ]
        found += [str(rel / f) for f in files if fnmatch.fnmatch(f, "*brief*.md")]
    return found


def find_brief(ws: Path) -> tuple[Path | None, str]:
    found = sorted(p for pattern in BRIEF_GLOBS for p in ws.glob(pattern))
    where = " or ".join(BRIEF_GLOBS)
    if not found:
        # Name what was written instead, so a failed run shows where it went.
        elsewhere = sorted(_stray_briefs(ws))[:5]
        answer = ws / ANSWER_PATH
        hint = f"; found instead: {elsewhere}" if elsewhere else ""
        if answer.is_file():
            hint += f"; {ANSWER_PATH} starts: {answer.read_text()[:120]!r}"
        return None, f"no brief at {where}{hint}"
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
    # The value question is the one pick-any block: its options are exactly
    # the five value drivers, and one or two of them are recommended.
    # A sixth, last option "Other (say which)" takes the user's own words.
    texts = [_norm(_OPTION.match(lines[i]).group(2)) for i in options]
    has_other = bool(texts) and texts[-1].startswith(OTHER)
    driver_options = options[:-1] if has_other else options
    leads = [next((d for d in VALUE_DRIVERS if t.startswith(d)), None) for t in texts[:len(driver_options)]]
    value_block = len(driver_options) == len(VALUE_DRIVERS) and set(leads) == set(VALUE_DRIVERS)
    if value_block and has_other and _RECOMMENDED.search(lines[options[-1]]):
        return False, "the 'Other' option is never recommended: the skill cannot recommend a value it did not hear"
    if not value_block and not 2 <= len(options) <= 4:
        return False, f"expected 2-4 option lines '- A. ...', found {len(options)}"
    if any(i < q_idx[0] for i in options):
        return False, "an option line appears before the question line"

    recommended_lines = [i for i, ln in enumerate(lines) if _RECOMMENDED.search(ln)]
    recommended_count = sum(len(_RECOMMENDED.findall(lines[i])) for i in recommended_lines)
    if value_block and not 1 <= recommended_count <= 2:
        return False, f"the value-driver question takes one or two '**(Recommended)**' tags, found {recommended_count}"
    if not value_block and recommended_count != 1:
        return False, f"expected exactly one '**(Recommended)**' tag, found {recommended_count}"
    if any(i not in options for i in recommended_lines):
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

    ``inputs`` maps each file the task provided to the CSV columns that
    identify something in it (empty for files that are not tables). A sketch row identified by one of
    a file's columns must cite that file in its Evidence cell, every citation
    of an input file carries a locator, and every file must be the evidence
    for at least one row.

    ``sources`` optionally binds a file to the sketch rows whose facts the
    task put in it: every row whose Node kind matches the file's pattern must
    cite that file, and at least one row must match, so a brief cannot pass
    by leaving those rows out. Patterns are tried in order and the first
    match binds the row, so overlapping words cannot demand two files.
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
                break  # first match binds the row; later patterns do not apply
    for name in inputs:
        if name not in cited:
            return False, f"no sketch row cites {name} as evidence"
    for name, pattern in sources.items():
        if name not in matched:
            kinds = sorted({_clean(r.get(kind_col, "")) for r in rows})
            return False, (
                f"no sketch row has a node kind matching {pattern.pattern!r}, the facts {name} holds; "
                f"the sketch has {kinds}"
            )
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
        handoff = _clean(row[handoff_col])
        if not handoff:
            return False, f"F{position} has an empty Handoff cell"
        if _is_placeholder(handoff):
            return False, f"F{position} has a placeholder Handoff cell: {handoff!r}"

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
        items = _artifacts(row[art_col])
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
    """Identity, source of truth and owner are answered or reference an open item.

    Every row also names its evidence, so a node kind nobody asked for shows.
    """
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
    ev_col = _column(headers, "evidence")
    if ev_col is None:
        return False, "sketch table has no 'evidence' column"
    for row in rows:
        kind = _clean(row.get(kind_col, "")) or "?"
        evidence = _clean(row.get(ev_col, ""))
        if _is_placeholder(evidence):
            return False, f"{kind}: Evidence is {evidence!r}; name the file, answer or reference design it came from"
        for header, cell in row.items():
            mark = _DRAFT_MARK.search(_clean(cell))
            if mark:
                return False, f"{kind}: {header} still carries {mark.group(0).lower()} from the draft; confirm it or make it an open item"
        for name, col in columns.items():
            value = _clean(row.get(col, ""))
            ref = _OPEN_REF.search(value)
            if ref:
                if ref.group(1).upper() not in open_ids:
                    return False, f"{kind}: {name} references {ref.group(1)}, which is not in Open items"
                continue
            if _is_placeholder(value):
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
            texts = "; ".join(_clean(r[dec_col])[:90] for r in matching)
            return False, (
                f"the decision about {label} is tagged {found[0]!r}; the transcript makes it {tag!r} "
                f"(rows: {texts!r})"
            )
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
    feature, labelled with its ID, its Feature name and exactly its artifacts,
    and one arrow from each feature it depends on.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    headers, rows = first_table(parts.get(FEATURES_HEADING, ""))
    id_col = _column(headers, "id")
    name_col = _column(headers, "feature")
    art_col = _column(headers, "artifacts")
    dep_col = _column(headers, "depends on")
    if not rows or None in (id_col, name_col, art_col, dep_col):
        return False, "Features table has no 'ID', 'Feature', 'Artifacts' and 'Depends on' columns"
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
        ids = _FEATURE_ID.findall(_clean(row[id_col]))
        fid = f"F{ids[0]}" if ids else "?"
        table_ids.append(fid)
        for dep in _FEATURE_ID.findall(_clean(row[dep_col])):
            want_edges.add((f"F{dep}", fid))
        if fid in by_feature:
            label = nodes[by_feature[fid]].lower()
            name = _clean(row[name_col]).lower()
            named = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", label) if name else None
            if not named:
                return False, f"plan map node for {fid} does not name the feature '{_clean(row[name_col])}'"
            # Read artifacts from what is left once the name is removed, so
            # a feature called 'Menus' or 'Policy check' cannot supply them.
            label_words = set(re.findall(r"[a-z]+", label[: named.start()] + " " + label[named.end():]))
            want = set(_artifacts(row[art_col]))
            missing = sorted(want - label_words)
            if missing:
                return False, f"plan map node for {fid} does not show its artifacts {missing}"
            extra = sorted((label_words & ARTIFACT_TYPES) - want)
            if extra:
                return False, f"plan map node for {fid} shows artifacts {extra} the table does not list"
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
    # Split on commas outside parentheses: "AccessPoint (many, where it
    # broadcasts)" is one peer, not two.
    for item in _citations(cell):
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
# Rule: brief-reference-design  (artifact: the brief)
# --------------------------------------------------------------------------

REFERENCE_HEADING = "reference design"
# The names in the skill's references/reference-designs.md table. The grading
# sandbox has no copy of the skill, so the grader keeps this list;
# tests/graders/test_designing_models_lib.py fails when the two differ.
REFERENCE_DESIGNS = frozenset({
    "infrahub-demo-dc",
    "infrahub-demo-service-catalog",
    "infrahub-solution-ai-dc",
    "infrahub-demo-sp",
    "infrahub-demo-otn",
    "infrahub-demo-reachability-check",
})
REFERENCE_DESIGNS_FILE = Path("skills/infrahub-designing-models/references/reference-designs.md")


# A design found at run time that the table does not list yet: accepted only
# as a full URL into the opsmill organisation, never as a bare name.
_DISCOVERED_REPO = re.compile(r"^https?://github\.com/opsmill/infrahub-(?:demo|solution)-[a-z0-9-]+/?$")
# A published schema or collection, e.g. infrahub/base-schemas.
_MARKETPLACE_ID = re.compile(r"\b[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*\b")
_LABEL_LINE = re.compile(
    r"^\s*(?:[-*]\s*)?\**\s*(closest|reused|different|marketplace)\s*\**\s*:\s*\**\s*(.*?)\s*$", re.IGNORECASE
)


def reference_design_names_in(text: str) -> set[str]:
    """The names in the first column of a reference-design table."""
    headers, rows = first_table(text)
    name_col = _column(headers, "name")
    if name_col is None:
        return set()
    return {_clean(r[name_col]).lower() for r in rows if _clean(r[name_col])}


def check_reference_design(ws: Path) -> tuple[bool, str]:
    """The brief names the closest reference design and what it reuses, or none with a reason."""
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if REFERENCE_HEADING not in parts:
        return False, "brief has no '## Reference design' section"
    labels: dict[str, str] = {}
    current: str | None = None
    for line in _lines_outside_fences(parts[REFERENCE_HEADING]):
        match = _LABEL_LINE.match(line)
        if match:
            current = match.group(1).lower()
            labels.setdefault(current, _clean(match.group(2)))
        elif current and line.strip() and (not labels.get(current) or re.match(r"\s*[-*]\s", line)):
            # A label's value in the bullets below it, every bullet kept.
            value = _clean(line.strip().lstrip("-*").strip())
            labels[current] = f"{labels[current]}; {value}" if labels.get(current) else value
    closest = labels.get("closest")
    if not closest:
        return False, "Reference design has no 'Closest:' line"
    marketplace = (labels.get("marketplace") or "").strip()
    if not marketplace:
        return False, "Reference design has no 'Marketplace:' line saying what the catalog offered"
    lowered = marketplace.lower()
    if lowered.startswith(("none", "not searched")):
        reason = re.sub(r"^(none( matched)?|not searched)\s*[:,(-]?\s*", "", lowered).strip(" .)")
        if not reason:
            return False, f"'Marketplace: {marketplace}' gives no reason"
    elif not _MARKETPLACE_ID.search(marketplace):
        return False, f"'Marketplace: {marketplace}' names no namespace/name schema, and is not 'none' or 'not searched' with a reason"
    else:
        # Each schema is followed by the node kinds it covers, before the next schema.
        ids = list(_MARKETPLACE_ID.finditer(marketplace))
        for i, m in enumerate(ids):
            end = ids[i + 1].start() if i + 1 < len(ids) else len(marketplace)
            covers = re.sub(r"\band\b|[^A-Za-z]", "", marketplace[m.end():end])
            if not covers:
                return False, f"'Marketplace:' names {m.group(0)} without the node kinds it covers"
    # The first word, read whole so a URL keeps its scheme; "none:" loses its colon.
    first = re.split(r"[\s(,;]", closest.strip(), maxsplit=1)[0].lower().rstrip(".:")
    if first == "none":
        reason = closest[len("none"):].strip(" :-,;.(")
        if not reason:
            return False, "'Closest: none' gives no reason"
        return True, "no reference design fits, with a reason"
    discovered = _DISCOVERED_REPO.match(first)
    name = re.sub(r"^https?://github\.com/opsmill/", "", first).strip("/")
    if name not in REFERENCE_DESIGNS and not discovered:
        return False, (
            f"'Closest: {closest}' is not a reference design listed in {REFERENCE_DESIGNS_FILE.name}, "
            "nor the full URL of an opsmill infrahub-demo-* or infrahub-solution-* repository"
        )
    if not labels.get("reused") or _is_placeholder(labels["reused"]):
        return False, f"the brief names {name} but its 'Reused:' line says nothing about what it follows"
    return True, f"closest reference design is {name}, with what it reuses"


# --------------------------------------------------------------------------
# Rules: brief-mechanisms-match-artifacts, brief-next-steps  (artifact: the brief)
# --------------------------------------------------------------------------

MECHANISMS_HEADING = "mechanisms"
NEXT_STEPS_HEADING = "next steps"
# The Mechanism column's values, from the skill's brief format.
MECHANISM_TYPES = {"generator", "check", "transform", "computed attribute", "resource pool", "schema constraint"}
# Artifacts that need a Mechanisms row saying what drives them and what they produce.
MECHANISM_ARTIFACTS = {"generator", "check", "transform"}
# How a Next step may name the skill that builds each artifact.
ARTIFACT_SKILLS = {
    "schema": ("schema manager", "infrahub-managing-schemas"),
    "objects": ("object manager", "infrahub-managing-objects"),
    "generator": ("generator manager", "infrahub-managing-generators"),
    "check": ("check manager", "infrahub-managing-checks"),
    "transform": ("transform manager", "infrahub-managing-transforms"),
    "menu": ("menu manager", "infrahub-managing-menus"),
}
# A step that passes the feature on: "Handoff", "hand off", "hand it off", or spec-kit.
# The data importer builds objects only from CSV or TSV files the brief lists in Inputs.
IMPORTER_NAMES = ("data importer", "infrahub-importing-data")
_TABULAR = re.compile(r"\.(?:csv|tsv)$", re.IGNORECASE)
_HANDOFF = re.compile(r"hand\s*-?\s*(?:it\s+)?off|/speckit\.specify", re.IGNORECASE)
_STEP = re.compile(r"^\s*(\d+)[.)]\s+(.*\S)\s*$")


def _features(parts: dict[str, str]) -> tuple[dict[str, set[str]], dict[str, set[str]], list[str], str]:
    """Feature ID -> artifacts, feature ID -> dependency IDs, IDs in table order."""
    headers, rows = first_table(parts.get(FEATURES_HEADING, ""))
    id_col, art_col, dep_col = _column(headers, "id"), _column(headers, "artifacts"), _column(headers, "depends on")
    if not rows or None in (id_col, art_col, dep_col):
        return {}, {}, [], "Features table has no 'ID', 'Artifacts' and 'Depends on' columns"
    arts, deps, order = {}, {}, []
    for row in rows:
        ids = _FEATURE_ID.findall(_clean(row[id_col]))
        if not ids:
            continue
        fid = f"F{ids[0]}"
        order.append(fid)
        arts[fid] = set(_artifacts(row[art_col]))
        deps[fid] = {f"F{d}" for d in _FEATURE_ID.findall(_clean(row[dep_col]))}
    return arts, deps, order, ""


def check_mechanisms_match_artifacts(ws: Path) -> tuple[bool, str]:
    """Every generator, check or transform a feature lists has a Mechanisms row, and back.

    F1's rows must say what drives them, what they produce and when they run,
    and a generator in F1 must be driven by a node kind from the sketch.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    arts, _, _, err = _features(parts)
    if err:
        return False, err
    if MECHANISMS_HEADING not in parts:
        return False, "brief has no '## Mechanisms' section"
    headers, rows = first_table(parts[MECHANISMS_HEADING])
    cols = {n: _column(headers, n) for n in ("feature", "behavior", "mechanism", "driven by", "produces", "runs when")}
    missing = [n for n, c in cols.items() if c is None]
    if missing:
        return False, f"Mechanisms table lacks columns {missing}"
    open_ids = _open_item_ids(parts)
    s_headers, s_rows, _ = _sketch(parts)
    kind_col = _column(s_headers, "node kind")
    sketch_kinds = {_clean(r[kind_col]).lower() for r in s_rows} if kind_col else set()

    seen: set[tuple[str, str]] = set()
    for row in rows:
        ids = _FEATURE_ID.findall(_clean(row[cols["feature"]]))
        mech = _clean(row[cols["mechanism"]]).lower()
        behavior = _clean(row[cols["behavior"]]) or "?"
        if len(ids) != 1:
            return False, f"Mechanisms row '{behavior}' names {len(ids)} features, expected one"
        fid = f"F{ids[0]}"
        if mech not in MECHANISM_TYPES:
            return False, f"Mechanisms row '{behavior}' has mechanism {mech!r}, not one of {sorted(MECHANISM_TYPES)}"
        if fid not in arts:
            return False, f"Mechanisms row '{behavior}' belongs to {fid}, which is not in the Features table"
        if mech in MECHANISM_ARTIFACTS and mech not in arts[fid]:
            return False, f"Mechanisms row '{behavior}' is a {mech} in {fid}, but {fid}'s Artifacts do not list {mech}"
        seen.add((fid, mech))
        if fid == "F1":
            for name in ("driven by", "produces", "runs when"):
                value = _clean(row[cols[name]])
                ref = _OPEN_REF.search(value)
                if ref and ref.group(1).upper() in open_ids:
                    continue
                if _is_placeholder(value):
                    return False, f"F1 mechanism '{behavior}' has no '{name}': {value!r}"
            if mech == "generator":
                words = set(re.findall(r"[a-z0-9_]+", _clean(row[cols["driven by"]]).lower()))
                if not words & sketch_kinds:
                    return False, f"F1 generator '{behavior}' is not driven by a node kind from the sketch"
    for fid, listed in arts.items():
        for mech in sorted(listed & MECHANISM_ARTIFACTS):
            if (fid, mech) not in seen:
                return False, f"{fid} lists {mech} in its Artifacts but has no {mech} row in Mechanisms"
    return True, "every generator, check and transform matches a Mechanisms row"


def check_uniqueness_is_schema_constraint(ws: Path, subject: re.Pattern) -> tuple[bool, str]:
    """The uniqueness rule the task asks for is a schema constraint, not a check.

    ``subject`` matches the Behavior of the row about that rule; at least one
    row must match, so leaving the rule out does not pass.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    headers, rows = first_table(parts.get(MECHANISMS_HEADING, ""))
    beh_col, mech_col = _column(headers, "behavior"), _column(headers, "mechanism")
    if not rows or beh_col is None or mech_col is None:
        return False, "Mechanisms table has no 'Behavior' and 'Mechanism' columns"
    matching = [r for r in rows if subject.search(_clean(r[beh_col]))]
    if not matching:
        return False, "no Mechanisms row covers the uniqueness rule the task asks for"
    # A pool row that hands out the values can sit beside the constraint;
    # any other mechanism enforcing the rule cannot.
    mechs = [(_clean(r[beh_col]), _clean(r[mech_col]).lower()) for r in matching]
    has_constraint = any(m == "schema constraint" for _, m in mechs)
    for behavior, mech in mechs:
        if mech not in {"schema constraint", "resource pool"} or not has_constraint:
            return False, f"'{behavior}' is a {mech}; the schema enforces uniqueness, so it is a schema constraint"
    return True, "the uniqueness rule is a schema constraint"


def check_next_steps_in_order(ws: Path) -> tuple[bool, str]:
    """Next steps take each feature once, after the features it depends on.

    Open items that F1's sketch refers to are settled in a step before F1.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if NEXT_STEPS_HEADING not in parts:
        return False, "brief has no '## Next steps' section"
    arts, deps, order, err = _features(parts)
    if err:
        return False, err
    steps = []
    for line in _lines_outside_fences(parts[NEXT_STEPS_HEADING]):
        match = _STEP.match(line)
        if match:
            steps.append(_clean(match.group(2)))
    if not steps:
        return False, "Next steps has no numbered steps"
    builders = {n for names in ARTIFACT_SKILLS.values() for n in names} | set(IMPORTER_NAMES)

    def settles_only(text: str) -> bool:
        # "Settle O1 before building F1" names F1 but is not F1's step:
        # it names an open item and neither hands off nor names a skill.
        low = text.lower()
        return bool(re.search(r"\bO\d+\b", text)) and not _HANDOFF.search(low) and not any(n in low for n in builders)

    first_step: dict[str, int] = {}
    open_step: dict[str, int] = {}
    for index, text in enumerate(steps):
        if not settles_only(text):
            for n in _FEATURE_ID.findall(text):
                first_step.setdefault(f"F{n}", index)
        for o in re.findall(r"\bO(\d+)\b", text):
            open_step.setdefault(f"O{o}", index)
    tabular = any(_TABULAR.search(name) for name in _input_files(parts))
    for fid in order:
        if fid not in first_step:
            return False, f"Next steps never take up {fid}"
        for dep in deps.get(fid, set()):
            if dep in first_step and first_step[dep] >= first_step[fid]:
                return False, f"Next steps take up {fid} before or with {dep}, which it depends on"
        text = steps[first_step[fid]].lower()
        if _HANDOFF.search(text):
            continue
        for artifact in sorted(arts.get(fid, set())):
            names = ARTIFACT_SKILLS.get(artifact, ())
            if artifact == "objects" and tabular:
                names += IMPORTER_NAMES
            if names and not any(n in text for n in names):
                return False, (
                    f"Next steps for {fid} neither hand it off nor name the skill for its {artifact} "
                    f"artifact: {steps[first_step[fid]][:160]!r}"
                )
    _, s_rows, _ = _sketch(parts)
    for row in s_rows:
        for cell in row.values():
            for ref in _OPEN_REF.findall(_clean(cell)):
                ref = ref.upper()
                if ref not in open_step or open_step[ref] >= first_step.get("F1", 0):
                    return False, f"F1's sketch waits on {ref}, but Next steps do not settle it before F1"
    return True, "Next steps take the features in dependency order, open items first"


# --------------------------------------------------------------------------
# Rule: brief-open-items-name-features  (artifact: the brief)
# --------------------------------------------------------------------------

_AFFECTS = re.compile(r"affects\s*:?\s*((?:`?F\d+`?(?:\s*(?:,|and|&)\s*)?)+)", re.IGNORECASE)


def _open_item_features(parts: dict[str, str]) -> dict[str, set[str]]:
    """Open item ID -> the feature IDs its 'affects' list names."""
    items: dict[str, set[str]] = {}
    for line in _lines_outside_fences(parts.get(OPEN_ITEMS_HEADING, "")):
        match = _OPEN_ITEM.match(line)
        if not match:
            continue
        affects = _AFFECTS.search(_clean(match.group(2)))
        ids = {f"F{n}" for n in _FEATURE_ID.findall(affects.group(1))} if affects else set()
        items[match.group(1).upper()] = ids
    return items


def check_open_items_name_features(ws: Path) -> tuple[bool, str]:
    """Each open item says which features its answer changes.

    Every item names at least one feature from the Features table, and every
    ``open: O<n>`` cell in the sketch or in Mechanisms belongs to a feature
    that item names, so a later answer shows which features it touches.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    _, _, order, err = _features(parts)
    if err:
        return False, err
    items = _open_item_features(parts)
    for oid, ids in sorted(items.items()):
        if not ids:
            return False, f"{oid} names no feature it affects ('affects F<n>')"
        unknown = sorted(ids - set(order))
        if unknown:
            return False, f"{oid} affects {unknown}, which are not in the Features table"

    def refs(heading: str, feature_col_name: str) -> list[tuple[str, str]]:
        headers, rows = first_table(parts.get(heading, ""))
        col = _column(headers, feature_col_name)
        found = []
        for row in rows:
            fids = _FEATURE_ID.findall(_clean(row.get(col, ""))) if col else []
            for cell in row.values():
                for ref in _OPEN_REF.findall(_clean(cell)):
                    found.append((ref.upper(), f"F{fids[0]}" if fids else "F1"))
        return found

    for oid, fid in refs(SKETCH_HEADING, "feature") + refs(MECHANISMS_HEADING, "feature"):
        if oid in items and fid not in items[oid]:
            return False, f"{fid} waits on {oid}, but {oid} does not list {fid} among the features it affects"
    return True, "every open item names the features its answer changes"


# --------------------------------------------------------------------------
# Rule: brief-value-drivers  (artifact: the brief)
# --------------------------------------------------------------------------

# The fixed list the value question offers and the brief names. It is the
# contract between the question block, the Value: line and the Value column,
# so it lives here as ARTIFACT_TYPES does, not as a copy of the rule's prose.
VALUE_DRIVERS = (
    "reduced engineering effort",
    "faster service delivery",
    "lower change failure costs",
    "less duplicated operational work",
    "reduced risk of service disruption",
)
BUSINESS_HEADING = "business"
_VALUE_LINE = re.compile(r"^\s*(?:[-*]\s+)?Value:\s*(.*?)\s*$", re.IGNORECASE)
# A value no driver fits, in the user's words: "Other: audit evidence (stated)".
_OTHER_ENTRY = re.compile(r"^Other:\s*(?P<text>[^()]*?)\s*\(\s*(?P<tag>stated|recommended)\b(?P<rest>.*)\)\s*$", re.IGNORECASE)
OTHER = "other"
_VALUE_ENTRY = re.compile(r"^(?P<driver>[^()]+?)\s*\(\s*(?P<tag>stated|recommended)\b(?P<rest>.*)\)\s*$", re.IGNORECASE)
_ANSWER_REF = re.compile(r"\banswer\s+Q\d+\b", re.IGNORECASE)
_REQUEST_REF = re.compile(r"\brequest\b", re.IGNORECASE)
# A file name's extension starts with a letter, so "1.5 days" is a figure.
_FILE_NAME = re.compile(r"[\w.\-/]*\w\.[A-Za-z][A-Za-z0-9]*")
# A figure written out in words counts the same as one in digits. "one" is
# left out: it is ordinary wording ("one row per VPN", "one source of truth").
# A number that starts a word ("40", "3.5", "30%", "3x", "$2M", "3h"), not
# digits inside a name such as L3VPN, IPv4, Q13 or AS65000.
_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)?")
_NUMBER_WORD = re.compile(
    r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"hundreds?|thousands?|millions?|dozens?|percent)\b|%",
    re.IGNORECASE,
)
_FILE_LOCATOR = re.compile(r"([\w.\-/]*\w\.[A-Za-z][A-Za-z0-9]*):\s*[^\s:;,)]+")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _clean(text)).strip().lower()


def _drivers_named(cell: str) -> list[str]:
    """Value drivers a cell names, in the order they appear."""
    text = _norm(cell)
    found = [(text.find(d), d) for d in VALUE_DRIVERS if d in text]
    # "Other" counts only as a list item of its own, not as a word in a
    # phrase such as "for other teams".
    other = re.search(r"(?:^|[,;/]|\band\b)\s*\bother\s*(?=$|[,;/]|\band\b)", text)
    if other:
        found.append((other.start(), OTHER))
    return [d for _, d in sorted(found)]


def _input_files(parts: dict[str, str]) -> set[str]:
    """Lower-cased names of the files the Inputs table lists."""
    headers, rows = first_table(parts.get(INPUTS_HEADING, ""))
    col = _column(headers, "file")
    return {n.lower() for row in rows for n in _file_names(row[col])} if col else set()


def _has_figure(text: str) -> bool:
    # Citations carry digits of their own (answer Q2, sites-2024.csv); a
    # number left after removing them is a figure.
    bare = _FILE_NAME.sub("", _ANSWER_REF.sub("", text))
    return bool(_NUMBER.search(bare) or _NUMBER_WORD.search(bare))


def _has_source(text: str, inputs: set[str]) -> bool:
    return bool(
        _ANSWER_REF.search(text) or _REQUEST_REF.search(text)
        or {Path(m.group(1)).name.lower() for m in _FILE_LOCATOR.finditer(text)} & inputs
    )


def _split_entries(line: str) -> list[str]:
    """Split a Value: line on ';' outside parentheses."""
    out, depth, current = [], 0, ""
    for ch in line:
        depth += ch == "("
        depth -= ch == ")" and depth > 0
        if ch == ";" and depth == 0:
            out.append(current.strip())
            current = ""
            continue
        current += ch
    out.append(current.strip())
    return [e for e in out if e]


def check_value_drivers(ws: Path) -> tuple[bool, str]:
    """The brief ranks the value drivers it serves, and each feature names one.

    Business has one `Value:` line: drivers from the fixed list in rank
    order, each tagged stated or recommended. A number is allowed only on a
    stated entry that cites where it came from. The Features table has a
    Value column naming drivers from that line, and F1 names the first.
    """
    parts, err = _brief_sections(ws)
    if parts is None:
        return False, err
    if BUSINESS_HEADING not in parts:
        return False, "brief has no '## Business' section"
    lines = [m.group(1) for ln in _lines_outside_fences(parts[BUSINESS_HEADING])
             if (m := _VALUE_LINE.match(_clean(ln)))]
    if len(lines) != 1:
        return False, f"expected one 'Value:' line in Business, found {len(lines)}"

    inputs = _input_files(parts)

    ranked: list[str] = []
    for entry in _split_entries(_clean(lines[0])):
        other = _OTHER_ENTRY.match(entry)
        if other:
            if other.group("tag").lower() != "stated":
                return False, "an 'Other' entry is always stated: it records a value the user named and no driver fits"
            if not other.group("text").strip():
                return False, "an 'Other' entry needs the user's own words after 'Other:'"
            words = other.group("text") + other.group("rest")
            if _has_figure(words) and not _has_source(words, inputs):
                return False, "the 'Other' entry gives a figure without its source (answer Q<n>, request, or <input file>:<locator>)"
            ranked.append(OTHER)
            continue
        match = _VALUE_ENTRY.match(entry)
        if not match:
            return False, f"'Value:' entry {entry[:60]!r} is not '<driver> (stated|recommended ...)'"
        driver = _norm(match.group("driver"))
        if driver not in VALUE_DRIVERS:
            return False, f"'Value:' entry {match.group('driver')!r} is not one of the five value drivers"
        rest = match.group("rest")
        if _has_figure(rest):
            if match.group("tag").lower() != "stated":
                return False, f"'Value:' entry '{driver}' gives a figure but is tagged recommended; only a figure the user stated may appear"
            if not _has_source(rest, inputs):
                return False, f"'Value:' entry '{driver}' gives a figure without its source (answer Q<n>, request, or <input file>:<locator>)"
        ranked.append(driver)

    headers, rows = first_table(parts.get(FEATURES_HEADING, ""))
    id_col, value_col = _column(headers, "id"), _column(headers, "value")
    if not rows or id_col is None:
        return False, "Features table has no 'ID' column"
    if value_col is None:
        return False, "Features table has no 'Value' column"
    for row in rows:
        ids = _FEATURE_ID.findall(_clean(row[id_col]))
        if not ids:
            continue
        fid, cell = f"F{ids[0]}", _clean(row[value_col])
        if _NUMBER.search(cell) or _NUMBER_WORD.search(cell):
            return False, f"{fid}'s Value cell gives a figure: {cell!r}; figures belong on the 'Value:' line with their source"
        named = _drivers_named(cell)
        if not named:
            return False, f"{fid}'s Value cell names no value driver: {cell!r}"
        extra = [d for d in named if d not in ranked]
        if extra:
            return False, f"{fid}'s Value cell names '{extra[0]}', which the 'Value:' line does not list"
        if fid == "F1" and ranked[0] not in named:
            return False, f"F1's Value cell does not name the first driver on the 'Value:' line, '{ranked[0]}'"
    return True, f"value drivers ranked ({', '.join(ranked)}), and every feature names one"


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

CHECKS: dict[str, Callable[[Path], tuple[bool, str]]] = {
    "one-question-recommended": check_one_question_recommended,
    "scope-split-f1-only": check_scope_split_f1_only,
    "features-artifacts": check_features_artifacts,
    "reference-design": check_reference_design,
    "mechanisms-match-artifacts": check_mechanisms_match_artifacts,
    "next-steps-in-order": check_next_steps_in_order,
    "open-items-name-features": check_open_items_name_features,
    "plan-map-matches": check_plan_map_matches,
    "model-map-matches": check_model_map_matches,
    "sketch-rows-complete": check_sketch_rows_complete,
    "decision-provenance": check_decision_provenance,
    "value-drivers": check_value_drivers,
}


def run_checks(
    names: list[str],
    workspace: Path,
    extra: dict[str, Callable[[Path], tuple[bool, str]]] | None = None,
    gate: tuple[str, ...] = (),
) -> dict:
    """Run named checks and return skillgrade JSON.

    ``extra`` supplies checks bound to a task's own inputs (for example the
    files a task provided), which have no place in the shared registry.
    ``gate`` names the checks the task exists for: one of them failing zeroes
    the score, so the other checks cannot carry the task past the threshold.
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
    if any(r["name"] in gate and not r["passed"] for r in results):
        score = 0.0
    failures = "; ".join(f"{r['name']}: {r['message']}" for r in results if not r["passed"])
    return {
        "score": round(score, 2),
        "details": failures or "all checks passed",
        "checks": results,
    }
