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

What the rule must carry, checked both ways:

1. A Markdown table with a kind column and a default column. Every SDK kind
   resolves through it, by its own row or an "every other kind" row, to the
   upstream default. No row names a kind or a value the SDK does not define.
2. No prose sentence outside that table states an omitted-`on_delete`
   default that contradicts upstream, or states one without naming the kind
   it applies to. That second part is what catches "If omitted, behavior
   defaults to `no-action`", which is wrong for exactly one kind.
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
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"^```.*?^```[ \t]*$", re.DOTALL | re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_VALUE = "|".join(re.escape(v) for v in VALUES)
_KIND_NAMES = "|".join(re.escape(k) for k in KINDS)

# A kind named in prose: `kind: Component`, `Component`, or the bare word.
_KIND_MENTION = re.compile(
    rf"(?:`kind:\s*({_KIND_NAMES})`|`({_KIND_NAMES})`|\b({_KIND_NAMES})\b)"
)
# "every other kind", "any other kind", "all other kinds", "non-Component".
_OTHER_MENTION = re.compile(
    r"\b(?:every|any|all)\s+other\s+(?:relationship\s+)?kinds?\b|\bnon-Component\b",
    re.I,
)
# A statement of the value applied when on_delete is omitted.
_DEFAULT_CLAIM = re.compile(
    rf"\b(?:defaults?|defaulted|resolves?|resolved)\s+(?:to\s+|is\s+)?`?({_VALUE})`?"
    rf"|\bdefault\s+(?:value\s+)?is\s+`?({_VALUE})`?",
    re.I,
)
# "cascade ... is opt-in": a claim that nothing cascades unless declared.
_OPT_IN_CLAIM = re.compile(r"\bcascade\b[^.]*?\bopt-in\b", re.I)
# A value in its own backticks, as opposed to inside `on_delete: <value>`.
_CODED_VALUE = re.compile(rf"`({_VALUE})`", re.I)

OTHER = "*other*"


def prose(text: str) -> str:
    """The rule without frontmatter and fenced blocks."""
    return _FENCE.sub("", _FRONTMATTER.sub("", text))


def default_tables(text: str) -> list[list[tuple[str, str]]]:
    """Rows of every table whose header has a kind column and a default column."""
    tables: list[list[tuple[str, str]]] = []
    lines = prose(text).splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        if len(block) < 3:
            continue
        header = [h.lower() for h in block[0]]
        kind_col = next((n for n, h in enumerate(header) if "kind" in h), None)
        default_col = next(
            (
                n
                for n, h in enumerate(header)
                if n != kind_col and ("default" in h or "omitted" in h)
            ),
            None,
        )
        if kind_col is None or default_col is None:
            continue
        tables.append(
            [
                (row[kind_col], row[default_col])
                for row in block[2:]
                if len(row) > max(kind_col, default_col)
            ]
        )
    return tables


def table_mapping(rows: list[tuple[str, str]]) -> tuple[dict[str, str], list[str]]:
    """Map each kind cell to the value its default cell states.

    Returns the mapping (kind name, or OTHER for an "every other kind" row)
    and the cells that name no known kind or no known value.
    """
    mapping: dict[str, str] = {}
    unknown: list[str] = []
    for kind_cell, default_cell in rows:
        value = re.search(rf"({_VALUE})", default_cell)
        kinds = {
            next(g for g in m.groups() if g) for m in _KIND_MENTION.finditer(kind_cell)
        }
        if _OTHER_MENTION.search(kind_cell):
            kinds.add(OTHER)
        if not kinds or value is None:
            unknown.append(f"{kind_cell} | {default_cell}")
            continue
        for kind in kinds:
            mapping[kind] = value.group(1)
    return mapping, unknown


def sentences(text: str) -> list[str]:
    """Prose sentences and list items, with tables and headings left out."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", prose(text)):
        lines = [
            ln for ln in para.splitlines() if not ln.lstrip().startswith(("|", "#"))
        ]
        items = re.split(r"\n\s*(?:[-*]|\d+\.)\s+", "\n" + "\n".join(lines))
        for item in items:
            flat = " ".join(item.split())
            out.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`*])", flat) if s)
    return out


def sentence_claims(sentence: str) -> list[tuple[str, str]]:
    """The (scope, value) default claims a sentence makes.

    Each kind mention is assigned to the claim nearest to it, so a sentence
    stating both defaults pairs each value with its own kind, whichever order
    it is written in. A claim no kind is assigned to has scope "" (unscoped).
    """
    claims: list[tuple[int, str]] = []
    spans: list[tuple[int, int]] = []
    for m in _DEFAULT_CLAIM.finditer(sentence):
        claims.append((m.start(), (m.group(1) or m.group(2)).lower()))
        spans.append(m.span())
    for m in _OPT_IN_CLAIM.finditer(sentence):
        claims.append((m.end(), RelationshipDeleteBehavior.NO_ACTION.value))
    if not claims:
        return []
    # A sentence that states a default once states it for every value it
    # coordinates with that claim ("resolves to `cascade` on Component and to
    # `no-action` on every other kind"). `on_delete: <value>` is a setting,
    # not a default, so it is left out.
    for m in _CODED_VALUE.finditer(sentence):
        if not any(start <= m.start() < end for start, end in spans):
            claims.append((m.start(), m.group(1).lower()))
    mentions = [
        (m.start(), next(g for g in m.groups() if g))
        for m in _KIND_MENTION.finditer(sentence)
    ]
    mentions += [(m.start(), OTHER) for m in _OTHER_MENTION.finditer(sentence)]
    scopes: dict[int, set[str]] = {n: set() for n in range(len(claims))}
    for pos, kind in mentions:
        nearest = min(range(len(claims)), key=lambda n: abs(claims[n][0] - pos))
        scopes[nearest].add(kind)
    result: list[tuple[str, str]] = []
    for n, (_, value) in enumerate(claims):
        if scopes[n]:
            result.extend((kind, value) for kind in sorted(scopes[n]))
        else:
            result.append(("", value))
    return result


def prose_problems(text: str) -> list[str]:
    """Default claims in prose that are unscoped or contradict upstream."""
    problems: list[str] = []
    for sentence in sentences(text):
        for scope, value in sentence_claims(sentence):
            if scope == "":
                problems.append(
                    f"states a default of {value!r} without naming a kind: {sentence!r}"
                )
            elif scope == OTHER:
                if value != UPSTREAM_OTHER:
                    problems.append(
                        f"says other kinds default to {value!r}: {sentence!r}"
                    )
            elif value != upstream_default(scope):
                problems.append(
                    f"says {scope} defaults to {value!r}, upstream applies {upstream_default(scope)!r}: {sentence!r}"
                )
    return problems


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
# The near misses are the cases that matter: one carries a correct table and
# keeps a wrong sentence; the other states `cascade` for Component in prose,
# so it contains the right words, and has its table backwards.
# ---------------------------------------------------------------------------

_CORRECT = """## Relationship Delete Behavior

When `on_delete` is omitted, Infrahub applies a default from the kind.

| Relationship kind | Default when `on_delete` is omitted |
| ----------------- | ----------------------------------- |
| `Component` | `cascade` |
| Every other kind | `no-action` |

A `kind: Component` relationship that omits `on_delete` resolves to
`cascade`, so deleting the owner deletes the peer.

```yaml
- name: servers
  kind: Component
  on_delete: no-action   # defaults to no-action would be wrong here
```
"""

# Same substance: a row per kind, the value written before the kind in
# prose, both defaults in one sentence, and a list item.
_CORRECT_VARIANT = """## Relationship Delete Behavior

| Omitted `on_delete` default | Kind |
| --- | --- |
| `no-action` | `Generic` |
| `no-action` | `Attribute` |
| `cascade` | `Component` |
| `no-action` | `Parent`, `Group`, `Hierarchy`, `Profile`, `Template` |

An omitted `on_delete` resolves to `cascade` on `kind: Component` and to
`no-action` on every other kind.

- Set `on_delete: no-action` explicitly on a Component relationship to a
  shared peer.
"""

_WRONG = """## Relationship Delete Behavior

| Value | Behavior |
| --- | --- |
| `cascade` | Deletes the peer |
| `no-action` | Keeps the peer |

A `kind: Component` relationship that omits `on_delete` defaults to
`no-action`. If omitted, behavior defaults to `no-action`.
"""

_NEAR_MISS_PROSE = """## Relationship Delete Behavior

| Relationship kind | Default when omitted |
| --- | --- |
| `Component` | `cascade` |
| Every other kind | `no-action` |

If omitted, behavior defaults to `no-action`.
"""

_NEAR_MISS_TABLE = """## Relationship Delete Behavior

| Relationship kind | Default when omitted |
| --- | --- |
| `Component` | `no-action` |
| Every other kind | `cascade` |

A `kind: Component` relationship that omits `on_delete` resolves to `cascade`.
"""


@pytest.mark.parametrize(
    ("label", "text", "expected"),
    [
        ("correct", _CORRECT, True),
        ("correct-variant", _CORRECT_VARIANT, True),
        ("wrong", _WRONG, False),
        ("near-miss-prose", _NEAR_MISS_PROSE, False),
        ("near-miss-table", _NEAR_MISS_TABLE, False),
    ],
    ids=["correct", "correct-variant", "wrong", "near-miss-prose", "near-miss-table"],
)
def test_parsers_grade_fixtures(label: str, text: str, expected: bool) -> None:
    ok = not table_problems(text) and not prose_problems(text)
    assert ok is expected, (
        f"fixture {label!r} graded wrong: {table_problems(text) + prose_problems(text)}"
    )


def test_opt_in_claim_scoped_to_component_fails() -> None:
    """The rule's old lead, "cascade behavior is opt-in", reads as a no-action default."""
    sentence = "It is independent of `kind: Component` and cascade behavior is opt-in."
    assert sentence_claims(sentence) == [("Component", "no-action")]


def test_explicit_value_without_default_verb_is_not_a_claim() -> None:
    """Advice to set a value explicitly states no default."""
    assert (
        sentence_claims(
            "Set `on_delete: no-action` explicitly on a `kind: Component` relationship."
        )
        == []
    )
