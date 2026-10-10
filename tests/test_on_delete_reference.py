"""The on_delete rule must state the default Infrahub applies when it is omitted.

`skills/infrahub-managing-schemas/rules/relationship-on-delete.md` tells an
agent what happens to peers when a node is deleted. When a relationship omits
`on_delete`, Infrahub fills it in at schema load from the relationship kind:
`cascade` for `kind: Component`, `no-action` for every other kind. The rule
said the opposite for Component ("defaults to `no-action`"), so an agent that
trusted it predicted that deleting an owner kept its Component peers, and the
peers were deleted (#190).

Why a pytest and not an eval task: this is the reference-drift case in
`dev/guidelines/rule-equals-test.md` § "When no task can score the rule".
Measured on #190, an eval task asking for the applied `on_delete` scored 1.0
with the wrong rule in place, because the model checked the claim against
the Infrahub source or docs.infrahub.app and overrode the skill. So the
test asserts the rule against upstream directly.

Upstream, in two parts:

- The kind and value sets come from `infrahub-sdk` (`RelationshipKind`,
  `RelationshipDeleteBehavior`), so a kind added upstream shows up here
  without editing this file.
- The kind-to-default mapping lives only in the server, so it is pinned:
  `backend/infrahub/core/schema/schema_branch.py` `process_relationships()`
  at infrahub-v1.11.4 (`e0ac367be9`), lines 1693-1711. It has been present
  since infrahub-v0.13.0, the first release with `on_delete`.

The pin is the limit of this test. It does not read the server, so it does
not fail on its own when the server changes which kind defaults to what.
Only a new kind or value in `infrahub-sdk` reaches it without an edit here.

What the rule must carry, checked both ways:

1. A Markdown table with a kind column and a default column. Every SDK kind
   resolves through it, by its own row or an "every other kind" row, to the
   upstream default. No row names a kind or a value the SDK does not define.
2. Every other unit of the rule (sentence, list item, heading, table row,
   comment inside a fence) that states a default states the upstream one,
   for a named kind. That catches "If omitted, behavior defaults to
   `no-action`", which is wrong for exactly one kind, and negated forms such
   as "does not resolve to `cascade`".
3. The parser fails closed: a unit about the omitted default that names no
   value is a failure, unless `EXEMPT` lists it with a reason.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from infrahub_sdk.schema.main import RelationshipDeleteBehavior, RelationshipKind

RULE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "infrahub-managing-schemas"
    / "rules"
    / "relationship-on-delete.md"
)

KINDS = tuple(k.value for k in RelationshipKind)
VALUES = tuple(v.value for v in RelationshipDeleteBehavior)

# Pinned from process_relationships() at infrahub-v1.11.4; see the docstring.
UPSTREAM_EXPLICIT = {
    RelationshipKind.COMPONENT.value: RelationshipDeleteBehavior.CASCADE.value
}
UPSTREAM_OTHER = RelationshipDeleteBehavior.NO_ACTION.value


def upstream_default(kind: str) -> str:
    return UPSTREAM_EXPLICIT.get(kind, UPSTREAM_OTHER)


# ---------------------------------------------------------------------------
# Parsing the rule
#
# The parser fails closed. Every unit of text (a prose sentence, a list item,
# a heading, a table row, a comment inside a fence) that talks about the
# omitted or default `on_delete`, or that names a kind next to a value, is
# classified. A unit about the default that names a kind but no value, or
# names nothing at all, is a failure, unless it is on EXEMPT with a reason.
# ---------------------------------------------------------------------------

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_FENCE_OPEN = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_KIND_NAMES = "|".join(re.escape(k) for k in KINDS)

# A kind named in prose or code: `kind: Component`, `Component`, the bare
# word. "non-Component" is not a mention of Component.
_KIND_MENTION = re.compile(rf"(?<![\w-])({_KIND_NAMES})(?![\w-])")
# "every other kind", "other relationship kinds", "non-Component".
_OTHER_MENTION = re.compile(
    r"\bother\s+(?:relationship\s+)?kinds?\b|(?<![\w-])non-Component\b", re.I
)


def _value_pattern(value: str) -> str:
    """A value, or for a verb-like value its inflections ("cascades")."""
    if value.endswith("e"):
        return rf"{re.escape(value[:-1])}(?:e|es|ed|ing)"
    return re.escape(value)


# A value in prose, backticked or bare.
_VALUES = [
    (re.compile(rf"(?<![\w-]){_value_pattern(v)}(?![\w-])", re.I), v) for v in VALUES
]
_VALUE_ALT = "|".join(re.escape(v) for v in VALUES)
# `on_delete: <value>` sets a value; it states no default.
_SETTING = re.compile(rf"\bon_delete\s*[:=]\s*[\"']?(?:{_VALUE_ALT})[\"']?", re.I)
# "cascade ... is opt-in": a claim that nothing cascades unless declared.
_OPT_IN_CLAIM = re.compile(r"\bcascade\b[^.]*?\bopt-in\b", re.I)
# Words that put a unit on the subject of the omitted or default on_delete.
_TOPIC = re.compile(
    r"\bomit\w*|\bdefault\w*|\bunless\s+(?:it\s+is\s+|explicitly\s+)?set\b"
    r"|\bnot\s+set\b|\bleft\s+(?:out|unset)\b|\bfall(?:s|ing)?\s+back\b"
    r"|\babsent\b|\bwithout\s+(?:an?\s+)?`?on_delete\b|\bno\s+`?on_delete\b"
    r"|\bfill(?:s|ed)?\s+(?:it\s+)?in\b|\bfilled-in\b|\bresolv\w*|\bimplicit\w*"
    r"|\bopt-in\b",
    re.I,
)
_NEGATION = re.compile(
    r"\bnot\b|n't\b|\bnever\b|\bno\s+longer\b|\brather\s+than\b|\binstead\s+of\b",
    re.I,
)
# A negation reaches back only to the start of its clause.
_CLAUSE_BREAK = re.compile(r"[;:,()|]")

OTHER = "*other*"

# Units of the rule that talk about the omitted default but state no value,
# each with the reason it is allowed to.
EXEMPT = {
    "When a relationship omits it, Infrahub fills it in from the relationship "
    "kind at schema load, and the schema it serves carries that value:": (
        "introduces the default table, which states the values"
    ),
}


def split_fences(text: str) -> tuple[list[str], list[str]]:
    """Split Markdown into prose lines and fenced code lines.

    Reads fences as Markdown does: a run of three or more backticks or tildes,
    indented or not (a fence under a list item is still a fence), closed by a
    run of the same character at least as long. An unclosed fence runs to the
    end of the text.
    """
    prose_lines: list[str] = []
    code_lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        if fence is None:
            m = _FENCE_OPEN.match(line)
            if m and not (m["fence"][0] == "`" and "`" in m["info"]):
                fence = m["fence"]
                prose_lines.append("")
                continue
            prose_lines.append(line)
        else:
            closer = re.fullmatch(
                rf"[ \t]*{re.escape(fence[0])}{{{len(fence)},}}[ \t]*", line
            )
            if closer:
                fence = None
                prose_lines.append("")
                continue
            code_lines.append(line)
    return prose_lines, code_lines


def _table_rows(lines: list[str]) -> list[tuple[list[str], bool]]:
    """Every table row as (cells, is_header), separator rows left out."""
    rows: list[tuple[list[str], bool]] = []
    first = True
    for line in lines:
        if not line.lstrip().startswith("|"):
            first = True
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        rows.append((cells, first))
        first = False
    return rows


def units(text: str) -> list[tuple[str, bool]]:
    """Every unit of text the rule states, as (text, is_table_header)."""
    body = _FRONTMATTER.sub("", text)
    prose_lines, code_lines = split_fences(body)
    out: list[tuple[str, bool]] = []
    out += [(" | ".join(cells), header) for cells, header in _table_rows(prose_lines)]
    paras: list[list[str]] = [[]]
    for line in prose_lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            out.append((stripped.lstrip("#").strip(), False))
            paras.append([])
        elif not stripped or stripped.startswith("|"):
            paras.append([])
        else:
            paras[-1].append(line)
    for para in paras:
        items = re.split(r"\n\s*(?:[-*]|\d+\.)\s+", "\n" + "\n".join(para))
        for item in items:
            flat = " ".join(item.split())
            out += [
                (s, False) for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`*])", flat) if s
            ]
    # A comment in a fence is prose; the code on its line gives it a scope.
    out += [
        (line.strip(), False) for line in code_lines if re.search(r"(?:^|\s)#", line)
    ]
    return out


def sentence_claims(sentence: str) -> list[tuple[str, str, bool]]:
    """The (scope, value, negated) default claims a unit makes.

    A unit makes claims when it is about the omitted default or names a kind.
    Every value in it, except one inside `on_delete: <value>`, is a claim.
    Each kind mention is assigned to the claim nearest to it, so a sentence
    stating both defaults pairs each value with its own kind. A claim no kind
    is assigned to has scope "" (unscoped). A claim is negated when "not" (or
    similar) stands between it and the start of its clause.
    """
    masked = _SETTING.sub(lambda m: " " * len(m.group()), sentence)
    hits: list[tuple[int, int, str]] = []
    for m in _OPT_IN_CLAIM.finditer(masked):
        hits.append((m.end(), m.end(), RelationshipDeleteBehavior.NO_ACTION.value))
        masked = masked[: m.start()] + " " * (m.end() - m.start()) + masked[m.end() :]
    for pattern, value in _VALUES:
        hits += [(m.start(), m.end(), value) for m in pattern.finditer(masked)]
    hits.sort()
    mentions = [(m.start(), m.group(1)) for m in _KIND_MENTION.finditer(masked)]
    mentions += [(m.start(), OTHER) for m in _OTHER_MENTION.finditer(masked)]
    if not hits or not (mentions or _TOPIC.search(sentence)):
        return []
    claims: list[tuple[int, str, bool]] = []
    prev_end = 0
    for start, end, value in hits:
        window = masked[prev_end:start]
        breaks = list(_CLAUSE_BREAK.finditer(window))
        if breaks:
            window = window[breaks[-1].end() :]
        claims.append((start, value, bool(_NEGATION.search(window))))
        prev_end = end
    scopes: dict[int, set[str]] = {n: set() for n in range(len(claims))}
    for pos, kind in mentions:
        nearest = min(range(len(claims)), key=lambda n: abs(claims[n][0] - pos))
        scopes[nearest].add(kind)
    result: list[tuple[str, str, bool]] = []
    for n, (_, value, negated) in enumerate(claims):
        for kind in sorted(scopes[n]) or [""]:
            result.append((kind, value, negated))
    return result


def unit_problems(unit: str, header: bool = False) -> list[str]:
    """What is wrong with one unit, or nothing."""
    claims = sentence_claims(unit)
    if not claims:
        if header or unit in EXEMPT or not _TOPIC.search(unit):
            return []
        masked = _SETTING.sub("", unit)
        if _KIND_MENTION.search(masked) or _OTHER_MENTION.search(masked):
            return [f"names a kind but no value for its default: {unit!r}"]
        return [f"talks about the default but names no kind or value: {unit!r}"]
    problems: list[str] = []
    for scope, value, negated in claims:
        verb = "does not default to" if negated else "defaults to"
        if scope == "":
            problems.append(f"says it {verb} {value!r} without naming a kind: {unit!r}")
            continue
        upstream = UPSTREAM_OTHER if scope == OTHER else upstream_default(scope)
        if (value == upstream) == negated:
            label = "other kinds" if scope == OTHER else scope
            problems.append(
                f"says {label} {verb} {value!r}, upstream applies {upstream!r}: {unit!r}"
            )
    return problems


def prose_problems(text: str) -> list[str]:
    """Default claims anywhere in the rule that are unscoped, wrong, or unreadable."""
    return [p for unit, header in units(text) for p in unit_problems(unit, header)]


def default_tables(text: str) -> list[list[tuple[str, str]]]:
    """Rows of every table whose header has a kind column and a default column."""
    prose_lines, _ = split_fences(_FRONTMATTER.sub("", text))
    tables: list[list[tuple[str, str]]] = []
    header: list[str] | None = None
    cols: tuple[int, int] | None = None
    for cells, is_header in _table_rows(prose_lines):
        if is_header:
            header = [h.lower() for h in cells]
            kind_col = next((n for n, h in enumerate(header) if "kind" in h), None)
            default_col = next(
                (
                    n
                    for n, h in enumerate(header)
                    if n != kind_col and ("default" in h or "omitted" in h)
                ),
                None,
            )
            cols = (
                None
                if kind_col is None or default_col is None
                else (kind_col, default_col)
            )
            if cols:
                tables.append([])
            continue
        if cols and len(cells) > max(cols):
            tables[-1].append((cells[cols[0]], cells[cols[1]]))
    return tables


def table_mapping(rows: list[tuple[str, str]]) -> tuple[dict[str, str], list[str]]:
    """Map each kind cell to the value its default cell states.

    Returns the mapping (kind name, or OTHER for an "every other kind" row)
    and the cells that name no known kind or no known value.
    """
    mapping: dict[str, str] = {}
    unknown: list[str] = []
    for kind_cell, default_cell in rows:
        values = [v for pattern, v in _VALUES if pattern.search(default_cell)]
        kinds = {m.group(1) for m in _KIND_MENTION.finditer(kind_cell)}
        if _OTHER_MENTION.search(kind_cell):
            kinds.add(OTHER)
        if not kinds or len(values) != 1:
            unknown.append(f"{kind_cell} | {default_cell}")
            continue
        for kind in kinds:
            mapping[kind] = values[0]
    return mapping, unknown


def table_problems(text: str) -> list[str]:
    """Both directions over the default table."""
    tables = default_tables(text)
    if not tables:
        return ["no table with a kind column and a default column"]
    mapping, unknown = table_mapping([row for table in tables for row in table])
    problems = [f"row names no known kind or value: {cell!r}" for cell in unknown]
    for kind in KINDS:
        stated = (
            mapping.get(kind, mapping.get(OTHER))
            if kind not in UPSTREAM_EXPLICIT
            else mapping.get(kind)
        )
        if stated is None:
            problems.append(f"{kind} has no default in the table")
        elif stated != upstream_default(kind):
            problems.append(
                f"table says {kind} defaults to {stated!r}, upstream applies {upstream_default(kind)!r}"
            )
    return problems


# ---------------------------------------------------------------------------
# The rule against upstream
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rule_text() -> str:
    return RULE.read_text(encoding="utf-8")


def test_pin_covers_only_sdk_kinds() -> None:
    """The pinned exceptions name kinds and values the SDK still defines."""
    assert set(UPSTREAM_EXPLICIT) <= set(KINDS)
    assert set(UPSTREAM_EXPLICIT.values()) | {UPSTREAM_OTHER} <= set(VALUES)


def test_rule_table_matches_upstream(rule_text: str) -> None:
    """Every SDK kind resolves, through the rule's table, to the upstream default."""
    problems = table_problems(rule_text)
    assert not problems, f"{RULE.name}: " + "; ".join(problems)


def test_rule_prose_matches_upstream(rule_text: str) -> None:
    """No sentence states an omitted-on_delete default that is unscoped or wrong."""
    problems = prose_problems(rule_text)
    assert not problems, f"{RULE.name}:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# The parsers, verified both ways against hand-written rules.
#
# Every reject case is _CORRECT with exactly one change, built by edit(), and
# asserts the exact problem lists, so a fixture that fails for a reason other
# than the one it names fails the test.
# ---------------------------------------------------------------------------

_SENTENCE = (
    "A `kind: Component` relationship that omits `on_delete` resolves to\n"
    "`cascade`, so deleting the owner deletes the peer."
)
_SENTENCE_FLAT = " ".join(_SENTENCE.split())

_CORRECT = f"""## Relationship Delete Behavior

| Relationship kind | Default when `on_delete` is omitted |
| ----------------- | ----------------------------------- |
| `Component` | `cascade` |
| Every other kind | `no-action` |

{_SENTENCE}

```yaml
- name: servers
  kind: Component
  on_delete: no-action   # keeps the servers when the service is deleted
```
"""

# Same substance: a row per kind, the value written before the kind, both
# defaults in one sentence, a negated claim that is true, a list item with
# a setting, the rule's advice sentence, and a comment that scopes itself.
_CORRECT_VARIANT = """## Relationship Delete Behavior

| Omitted `on_delete` default | Kind |
| --- | --- |
| `no-action` | `Generic` |
| `no-action` | `Attribute` |
| `cascade` | `Component` |
| `no-action` | `Parent`, `Group`, `Hierarchy`, `Profile`, `Template` |

An omitted `on_delete` resolves to `cascade` on `kind: Component` and to
`no-action` on every other kind. A `kind: Component` relationship does not
default to `no-action`.

- Set `on_delete: no-action` explicitly on a `kind: Component` relationship
  whose peers are shared or must outlive the owner. Omitting it on
  `kind: Component` means `cascade`, which is right for truly owned peers.

  ~~~yaml
  kind: Component   # with no on_delete, Component cascades
  ~~~
"""


def edit(old: str, new: str, base: str = _CORRECT) -> str:
    """_CORRECT with one change; fails if the target is not there."""
    assert base.count(old) == 1, f"edit target not found once: {old!r}"
    return base.replace(old, new)


def _says(scope: str, verb: str, value: str, unit: str) -> str:
    upstream = upstream_default(scope) if scope != "other kinds" else UPSTREAM_OTHER
    return f"says {scope} {verb} {value!r}, upstream applies {upstream!r}: {unit!r}"


_FENCED_CLAIM = "description: Component defaults to no-action"

ACCEPT = {
    "correct": _CORRECT,
    "correct-variant": _CORRECT_VARIANT,
    # Fence boundaries, inside side: a non-comment line in a fence is code.
    "fence-indented-tilde": edit(
        _SENTENCE, f"{_SENTENCE}\n\n- item\n\n  ~~~\n  {_FENCED_CLAIM}\n  ~~~"
    ),
    "fence-length-matched": edit(
        _SENTENCE, f"{_SENTENCE}\n\n````\n```\n{_FENCED_CLAIM}\n````"
    ),
}

# label -> (text, table_problems, prose_problems)
REJECT: dict[str, tuple[str, list[str], list[str]]] = {
    "wrong": (
        edit("resolves to\n`cascade`", "defaults to\n`no-action`"),
        [],
        [
            _says(
                "Component",
                "defaults to",
                "no-action",
                _SENTENCE_FLAT.replace(
                    "resolves to `cascade`", "defaults to `no-action`"
                ),
            )
        ],
    ),
    "near-miss-prose": (
        edit(_SENTENCE, "If omitted, behavior defaults to `no-action`."),
        [],
        [
            "says it defaults to 'no-action' without naming a kind: "
            "'If omitted, behavior defaults to `no-action`.'"
        ],
    ),
    "near-miss-table": (
        edit("| `Component` | `cascade` |", "| `Component` | `no-action` |"),
        ["table says Component defaults to 'no-action', upstream applies 'cascade'"],
        [_says("Component", "defaults to", "no-action", "`Component` | `no-action`")],
    ),
    # Paraphrases the earlier parser passed.
    "negated-cascade": (
        edit(
            _SENTENCE,
            "A `kind: Component` relationship that omits `on_delete` does not resolve to `cascade`.",
        ),
        [],
        [
            _says(
                "Component",
                "does not default to",
                "cascade",
                "A `kind: Component` relationship that omits `on_delete` does not resolve to `cascade`.",
            )
        ],
    ),
    "falls-back": (
        edit(_SENTENCE, "If omitted, `on_delete` falls back to `no-action`."),
        [],
        [
            "says it defaults to 'no-action' without naming a kind: "
            "'If omitted, `on_delete` falls back to `no-action`.'"
        ],
    ),
    "uses": (
        edit(
            _SENTENCE,
            "When omitted on a Component relationship, Infrahub uses `no-action`.",
        ),
        [],
        [
            _says(
                "Component",
                "defaults to",
                "no-action",
                "When omitted on a Component relationship, Infrahub uses `no-action`.",
            )
        ],
    ),
    "unless-set": (
        edit(_SENTENCE, "On `kind: Component`, `on_delete` is `no-action` unless set."),
        [],
        [
            _says(
                "Component",
                "defaults to",
                "no-action",
                "On `kind: Component`, `on_delete` is `no-action` unless set.",
            )
        ],
    ),
    # Table-header boundary: a table the default-table detector does not
    # recognise is still graded row by row, and so is a header row.
    "second-table": (
        edit(
            _SENTENCE,
            f"{_SENTENCE}\n\n| Relationship type | Applied value |\n| --- | --- |\n"
            "| `Component` | `no-action` |",
        ),
        [],
        [_says("Component", "defaults to", "no-action", "`Component` | `no-action`")],
    ),
    "claim-in-header-row": (
        edit(
            _SENTENCE,
            f"{_SENTENCE}\n\n| `Component` | `no-action` |\n| --- | --- |\n"
            "| `Generic` | `no-action` |",
        ),
        [],
        [_says("Component", "defaults to", "no-action", "`Component` | `no-action`")],
    ),
    # A comment inside a fence is prose.
    "fence-comment": (
        edit(
            "  kind: Component\n",
            "  kind: Component  # omitted on_delete defaults to no-action\n",
        ),
        [],
        [
            _says(
                "Component",
                "defaults to",
                "no-action",
                "kind: Component  # omitted on_delete defaults to no-action",
            )
        ],
    ),
    # Fence boundaries, outside side: the same line once the fence closes.
    "fence-indented-tilde-after": (
        edit(_SENTENCE, f"{_SENTENCE}\n\n- item\n\n  ~~~\n  ~~~\n  {_FENCED_CLAIM}"),
        [],
        [_says("Component", "defaults to", "no-action", _FENCED_CLAIM)],
    ),
    "fence-length-matched-after": (
        edit(_SENTENCE, f"{_SENTENCE}\n\n````\n```\n````\n{_FENCED_CLAIM}"),
        [],
        [_says("Component", "defaults to", "no-action", _FENCED_CLAIM)],
    ),
    # Fail closed: a sentence about the default that the parser cannot read.
    "kind-without-value": (
        edit(
            _SENTENCE,
            "A `kind: Component` relationship that omits `on_delete` keeps its peers.",
        ),
        [],
        [
            "names a kind but no value for its default: "
            "'A `kind: Component` relationship that omits `on_delete` keeps its peers.'"
        ],
    ),
    "nothing-named": (
        edit(_SENTENCE, "If omitted, Infrahub keeps the peers."),
        [],
        [
            "talks about the default but names no kind or value: "
            "'If omitted, Infrahub keeps the peers.'"
        ],
    ),
}


@pytest.mark.parametrize("label", sorted(ACCEPT))
def test_parsers_accept(label: str) -> None:
    text = ACCEPT[label]
    assert table_problems(text) == []
    assert prose_problems(text) == []


@pytest.mark.parametrize("label", sorted(REJECT))
def test_parsers_reject(label: str) -> None:
    text, expected_table, expected_prose = REJECT[label]
    assert table_problems(text) == expected_table
    assert prose_problems(text) == expected_prose


def test_opt_in_claim_scoped_to_component_fails() -> None:
    """The rule's old lead, "cascade behavior is opt-in", reads as a no-action default."""
    sentence = "It is independent of `kind: Component` and cascade behavior is opt-in."
    assert sentence_claims(sentence) == [("Component", "no-action", False)]


def test_explicit_value_without_default_verb_is_not_a_claim() -> None:
    """Advice to set a value explicitly states no default."""
    assert (
        sentence_claims(
            "Set `on_delete: no-action` explicitly on a `kind: Component` relationship."
        )
        == []
    )


def test_exempt_units_are_in_the_rule(rule_text: str) -> None:
    """An exemption for a sentence the rule no longer carries is dead."""
    present = {unit for unit, _ in units(rule_text)}
    assert set(EXEMPT) <= present


def test_advice_sentence_is_a_setting_then_a_true_default() -> None:
    """The rule's advice sets a value, then states the Component default."""
    assert (
        sentence_claims(
            "Set `on_delete: no-action` explicitly on a `kind: Component` relationship "
            "whose peers are shared or must outlive the owner."
        )
        == []
    )
    assert sentence_claims(
        "Omitting it on `kind: Component` means `cascade`, which is right for truly owned peers."
    ) == [("Component", "cascade", False)]
