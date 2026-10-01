"""Shared grader library for infrahub-managing-menus skill evaluations.

Provides YAML parsing helpers, individual assertion check functions, a CHECKS
registry, and the top-level ``run_checks`` function that returns skillgrade
JSON format.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["apiversion-and-kind", "spec-data-structure", "name-and-namespace"],
        Path("outputs/task-1/menu.yml"),
    )
    print(result)  # {"score": 0.67, "details": "...", "checks": [...]}
"""

from __future__ import annotations

import json
import re
import shlex
import textwrap
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# Infrahub's built-in menu tree
#
# Source of truth is Infrahub itself: ``default_menu`` in
# ``backend/infrahub/menu/menu.py``, verified at tag ``infrahub-v1.11.2``
# (ee269fe2e64cf511d77c431fc6eb58a870d794d7). Every entry there is namespace
# ``Builtin`` and ``protected=True``. ``menu/models.py`` computes an item's
# identifier as ``f"{namespace}{name}"``, which is what these keys hold.
#
# That concatenated string is NOT the value ``parent:`` takes in a menu file,
# despite ``docs/docs/reference/menu.mdx`` saying so — see
# ``_parent_identifier`` below for the measurement. Do not re-derive the
# spelling from that page.
#
# This mapping and the table in ``rules/hierarchy-nesting.md`` are both copies
# of the upstream list, and ``test_rule_tables_match_the_constant`` pins them
# to each other, so editing one fails until the other follows. Re-read menu.py
# at the current tag, then change both.
# ---------------------------------------------------------------------------

BUILTIN_MENU_SECTIONS: dict[str, str] = {
    "BuiltinOther": "Other",
    "BuiltinIPAM": "IPAM",
    "BuiltinProposedChanges": "Proposed Changes",
    "BuiltinBranches": "Branches",
    "BuiltinObjectManagement": "Object Management",
    "BuiltinActions": "Actions",
    "BuiltinIntegration": "Integrations",
    "BuiltinActivity": "Activity",
    "BuiltinAdmin": "Admin",
}

# The two sections carrying ``section=MenuSection.OBJECT`` in ``default_menu``
# (menu.py:31 and :51). The other seven are ``MenuSection.INTERNAL``: platform
# features, not somewhere user object nodes belong.
OBJECT_AREA_SECTIONS: frozenset[str] = frozenset({"BuiltinOther", "BuiltinIPAM"})


# ---------------------------------------------------------------------------
# Low-level menu traversal helpers
# ---------------------------------------------------------------------------


def _menu_items(doc: dict) -> list[dict]:
    """Return top-level menu items from spec.data."""
    return doc.get("spec", {}).get("data", []) or []


def _all_menu_leaves(doc: dict) -> list[dict]:
    """Recursively collect all leaf menu items (items with a 'kind' key)."""
    leaves: list[dict] = []

    def _walk(items: list) -> None:
        for item in (items or []):
            if item.get("kind"):
                leaves.append(item)
            children = item.get("children", {})
            if isinstance(children, dict):
                _walk(children.get("data", []))
            elif isinstance(children, list):
                _walk(children)

    _walk(_menu_items(doc))
    return leaves


def _all_menu_items_recursive(doc: dict) -> list[dict]:
    """Recursively collect all menu items at every level."""
    items: list[dict] = []

    def _walk(item_list: list) -> None:
        for item in (item_list or []):
            items.append(item)
            children = item.get("children", {})
            if isinstance(children, dict):
                _walk(children.get("data", []))
            elif isinstance(children, list):
                _walk(children)

    _walk(_menu_items(doc))
    return items


def _child_items(item: dict) -> list[dict]:
    """Return an item's direct children, tolerating both children shapes."""
    children = item.get("children", {})
    if isinstance(children, dict):
        return children.get("data", []) or []
    if isinstance(children, list):
        return children
    return []


def _subtree(item: dict) -> list[dict]:
    """Return an item plus every descendant beneath it."""
    collected = [item]
    for child in _child_items(item):
        collected.extend(_subtree(child))
    return collected


def _identifier(item: dict) -> str:
    """Return the menu item's identifier: namespace concatenated with name."""
    return f"{item.get('namespace') or ''}{item.get('name') or ''}"


def _declares_parent(item: dict) -> bool:
    """Whether the item declares a parent at all, resolvable or not.

    An item that names a parent is not rendered at the top level, so it cannot
    duplicate a top-level heading — and if the reference is malformed the item
    does not load at all. Either way it is out of scope for the recreate check.
    """
    parent = item.get("parent")
    return bool(parent) if isinstance(parent, (str, list)) else False


def _parent_identifier(item: dict) -> str:
    """Return the built-in section this item attaches to, or an empty string.

    A menu file is loaded through the generic object spec, so ``parent`` is a
    cardinality-one relationship reference resolved by human-friendly ID.
    ``CoreMenu``'s HFID is two components, ``[namespace__value, name__value]``,
    and only a two-element list survives that:

        >>> from infrahub_sdk.spec.object import normalize_hfid_reference
        >>> normalize_hfid_reference("BuiltinIPAM")        # 1 element
        ['BuiltinIPAM']
        >>> normalize_hfid_reference(["Builtin", "IPAM"])  # 2 elements
        ['Builtin', 'IPAM']

    Measured on infrahub-sdk 1.23.2. The backend compares those lengths before
    it queries anything (``core/manager.py``: ``if
    len(node_schema.human_friendly_id) != len(hfid): raise NodeNotFoundError``),
    so the concatenated string cannot resolve whatever the data holds. Infrahub's
    own ``docs/docs/reference/menu.mdx`` documents the string form; it is wrong
    on this point, which is why anything but a two-element list returns "" here.
    """
    parent = item.get("parent")
    if isinstance(parent, list) and len(parent) == 2 and all(isinstance(p, str) for p in parent):
        return "".join(p.strip() for p in parent)
    return ""


def _normalized(value: Any) -> str:
    """Lowercase and strip non-alphanumerics, for comparing display labels."""
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value.lower() if ch.isalnum())


_BUILTIN_LABELS: dict[str, str] = {
    _normalized(label): label for label in BUILTIN_MENU_SECTIONS.values()
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output(path: Path) -> tuple[dict, str]:
    """Load a YAML menu file and return ``(parsed_dict, raw_text)``.

    If the file does not exist or cannot be parsed, returns ``({}, "")``.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}, ""

    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        parsed = {}

    return parsed, raw


# ---------------------------------------------------------------------------
# Individual check functions
#
# Each check has the signature:
#     check_*(doc: dict, **kwargs) -> tuple[bool, str]
#
# where the bool is True on pass, and str is a human-readable message.
# ---------------------------------------------------------------------------


def check_apiversion_and_kind(doc: dict, **_: Any) -> tuple[bool, str]:
    """apiVersion: infrahub.app/v1 and kind: Menu."""
    api = doc.get("apiVersion")
    kind = doc.get("kind")
    if api == "infrahub.app/v1" and kind == "Menu":
        return True, "apiVersion: infrahub.app/v1 and kind: Menu"
    return False, f"apiVersion: {api}, kind: {kind}"


def check_spec_data_structure(doc: dict, **_: Any) -> tuple[bool, str]:
    """Items under spec.data as list."""
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        return False, "No spec key or spec is not a dict"
    data = spec.get("data")
    if not isinstance(data, list):
        return False, f"spec.data is {type(data).__name__}, expected list"
    if len(data) == 0:
        return False, "spec.data is empty"
    return True, f"spec.data is a list with {len(data)} items"


def check_name_and_namespace(doc: dict, **_: Any) -> tuple[bool, str]:
    """Every item has name and namespace."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    missing: list[str] = []
    for item in all_items:
        label = item.get("label", item.get("name", "?"))
        if not item.get("name"):
            missing.append(f"{label} missing name")
        if not item.get("namespace"):
            missing.append(f"{label} missing namespace")
    if missing:
        return False, f"Issues: {', '.join(missing)}"
    return True, "All items have name and namespace"


def check_kind_for_schema_links(doc: dict, **_: Any) -> tuple[bool, str]:
    """Items use kind, not path."""
    leaves = _all_menu_leaves(doc)
    if not leaves:
        return False, "No leaf items with kind found"
    for item in leaves:
        if item.get("path") and not item.get("kind"):
            return False, f"Item {item.get('name')} uses path instead of kind"
    return True, f"{len(leaves)} items use kind for schema links"


def check_mdi_icons(doc: dict, **_: Any) -> tuple[bool, str]:
    """All icons use mdi: prefix."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    bad: list[str] = []
    for item in all_items:
        icon = item.get("icon", "")
        if not icon:
            bad.append(f"{item.get('name', '?')} has no icon")
        elif not icon.startswith("mdi:"):
            bad.append(f"{item.get('name', '?')} icon '{icon}' missing mdi: prefix")
    if bad:
        return False, f"Icon issues: {', '.join(bad)}"
    return True, "All icons use mdi: prefix"


def check_labels_present(doc: dict, **_: Any) -> tuple[bool, str]:
    """Each item has label."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    missing: list[str] = []
    for item in all_items:
        if not item.get("label"):
            missing.append(item.get("name", "?"))
    if missing:
        return False, f"Missing label on: {', '.join(missing)}"
    return True, "All items have labels"


def check_group_headers_no_kind(doc: dict, **_: Any) -> tuple[bool, str]:
    """Group headers have no kind/path."""
    groups = [
        i for i in _menu_items(doc)
        if i.get("children") and not i.get("kind") and not i.get("path")
    ]
    if not groups:
        return False, "No top-level group headers without kind/path found"
    bad = [
        g.get("name", "?") for g in _menu_items(doc)
        if g.get("children") and (g.get("kind") or g.get("path"))
    ]
    if bad:
        return False, f"Group headers with kind/path: {', '.join(bad)}"
    return True, f"{len(groups)} group headers without kind/path"


def check_children_data_wrapper(doc: dict, **_: Any) -> tuple[bool, str]:
    """Children use children.data wrapper."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"
    for item in all_items:
        children = item.get("children")
        if children is None:
            continue
        if isinstance(children, list):
            return (
                False,
                f"Item {item.get('name', '?')} has children as a list, "
                f"expected children.data wrapper",
            )
        if isinstance(children, dict) and "data" in children:
            continue
        return False, f"Item {item.get('name', '?')} has children but no data key"
    return True, "All children use children.data wrapper"


def check_leaf_items_have_kind(doc: dict, **_: Any) -> tuple[bool, str]:
    """Leaf items use kind."""
    leaves = _all_menu_leaves(doc)
    if not leaves:
        # Check if there are any items without children that also lack kind
        for item in _all_menu_items_recursive(doc):
            if not item.get("children") and not item.get("kind"):
                return False, f"Leaf item {item.get('name', '?')} has no kind"
        return False, "No leaf items found"
    return True, f"{len(leaves)} leaf items have kind"


def check_correct_grouping(doc: dict, **_: Any) -> tuple[bool, str]:
    """Server/Switch/PDU under Infrastructure, Manufacturer/Provider under Organization."""
    groups: dict[str, list[str]] = {}
    for item in _menu_items(doc):
        label = (item.get("label") or item.get("name") or "").lower()
        children = item.get("children", {})
        if isinstance(children, dict):
            child_list = children.get("data", [])
        elif isinstance(children, list):
            child_list = children
        else:
            child_list = []
        child_kinds = [c.get("kind", "").lower() for c in child_list]
        groups[label] = child_kinds

    infra_kinds = groups.get("infrastructure", [])
    org_kinds = groups.get("organization", [])

    issues: list[str] = []
    for expected in ["dcimserver", "dcimswitch", "dcimpdu"]:
        if not any(expected in k for k in infra_kinds):
            issues.append(f"{expected} not under Infrastructure")
    for expected in ["organizationmanufacturer", "organizationprovider"]:
        if not any(expected in k for k in org_kinds):
            issues.append(f"{expected} not under Organization")

    if issues:
        return False, "; ".join(issues)
    return True, "Correct grouping: infra and org items under right headers"


def check_all_nodes_present(doc: dict, **_: Any) -> tuple[bool, str]:
    """All 5 nodes present."""
    expected = {
        "DcimServer",
        "DcimSwitch",
        "DcimPdu",
        "OrganizationManufacturer",
        "OrganizationProvider",
    }
    found: set[str] = set()
    for item in _all_menu_items_recursive(doc):
        kind = item.get("kind", "")
        if kind in expected:
            found.add(kind)
    missing = expected - found
    if missing:
        return False, f"Missing nodes: {', '.join(sorted(missing))}"
    return True, f"All {len(expected)} nodes present"


def check_contextual_icons(doc: dict, **_: Any) -> tuple[bool, str]:
    """Icons are contextually appropriate (mdi: prefix)."""
    for item in _all_menu_items_recursive(doc):
        icon = item.get("icon", "")
        if not icon.startswith("mdi:"):
            return False, f"{item.get('name', '?')} icon missing mdi: prefix"
    items = _all_menu_items_recursive(doc)
    if not items:
        return False, "No menu items found"
    return True, f"All {len(items)} items have mdi: icons"


def check_generic_kind_link(doc: dict, **_: Any) -> tuple[bool, str]:
    """Menu item uses kind: LocationGeneric."""
    for item in _all_menu_items_recursive(doc):
        kind = item.get("kind", "")
        if "generic" in kind.lower() or kind == "LocationGeneric":
            return True, f"Item {item.get('name', '?')} uses kind: {kind}"
    return False, "No menu item with kind referencing a Generic"


def check_location_children(doc: dict, **_: Any) -> tuple[bool, str]:
    """Individual location types as children."""
    location_types = {"region", "site", "room", "rack"}
    found: set[str] = set()
    for item in _all_menu_items_recursive(doc):
        kind = (item.get("kind") or "").lower()
        name = (item.get("name") or "").lower()
        for loc in location_types:
            if loc in kind or loc in name:
                found.add(loc)
    missing = location_types - found
    if missing:
        return False, f"Missing location children: {', '.join(sorted(missing))}"
    return True, "All location types present as children"


def check_separate_devices_section(doc: dict, **_: Any) -> tuple[bool, str]:
    """Devices separate from Locations."""
    for item in _menu_items(doc):
        label = (item.get("label") or item.get("name") or "").lower()
        kind = (item.get("kind") or "").lower()
        children = item.get("children", {})
        if isinstance(children, dict):
            child_list = children.get("data", [])
        elif isinstance(children, list):
            child_list = children
        else:
            child_list = []
        child_kinds = [(c.get("kind") or "").lower() for c in child_list]
        if "device" in label or "device" in kind or any("device" in k for k in child_kinds):
            # Check it's not under a locations group
            if "location" not in label:
                return (
                    True,
                    f"Devices found in separate section: {item.get('label', item.get('name'))}",
                )
    return False, "No separate devices section found"


def check_include_in_menu_false(doc: dict, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Advises include_in_menu: false (checks raw text)."""
    if "include_in_menu" in raw_text:
        return True, "include_in_menu mentioned in output"
    return False, "No mention of include_in_menu in output"


def check_infrahub_yml_registration(doc: dict, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Mentions .infrahub.yml (checks raw text)."""
    if ".infrahub.yml" in raw_text or "infrahub.yml" in raw_text:
        return True, ".infrahub.yml registration mentioned in output"
    return False, "No mention of .infrahub.yml registration in output"


def check_schema_comment(doc: dict, raw_text: str = "", **_: Any) -> tuple[bool, str]:
    """Has $schema or yaml-language-server comment (checks raw text)."""
    if "$schema" in raw_text or "yaml-language-server" in raw_text:
        return True, "$schema comment found in raw YAML"
    return False, "No $schema or yaml-language-server comment found"


def check_no_builtin_section_recreated(doc: dict, **_: Any) -> tuple[bool, str]:
    """No menu item duplicates a section Infrahub already ships."""
    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"

    collisions: list[str] = []

    for item in all_items:
        identifier = _identifier(item)
        if identifier in BUILTIN_MENU_SECTIONS:
            collisions.append(
                f"item '{identifier}' reuses the identifier of the built-in "
                f"{BUILTIN_MENU_SECTIONS[identifier]} section"
            )

    # Object nodes belong in the object area. Attaching them to a platform
    # section buries user data in Infrahub's own part of the sidebar.
    #
    # Only shipped sections are judged here: `parent` takes any CoreMenu HFID,
    # so parenting to a group of your own is ordinary nesting, and a misspelled
    # built-in is a lookup failure that `parent-attaches-to-builtin` reports.
    for item in all_items:
        target = _parent_identifier(item)
        if target in BUILTIN_MENU_SECTIONS and target not in OBJECT_AREA_SECTIONS:
            if any(child.get("kind") for child in _subtree(item)):
                collisions.append(
                    f"'{_identifier(item)}' attaches object content to "
                    f"{target}, a platform section; only "
                    f"{', '.join(sorted(OBJECT_AREA_SECTIONS))} hold object data"
                )

    # A top-level entry that declares a parent is not top level in the rendered
    # sidebar — it attaches under that parent, so it cannot collide.
    for item in _menu_items(doc):
        if _declares_parent(item):
            continue
        # The sidebar renders `label`, so that is what can duplicate a shipped
        # heading. `name` only matters when no label is there to override it:
        # a "Device Actions" group whose name happens to be "Actions" shows no
        # duplicate and must not be flagged.
        field = "label" if item.get("label") else "name"
        match = _BUILTIN_LABELS.get(_normalized(item.get(field)))
        if match:
            collisions.append(
                f"top-level {field} '{item.get(field)}' recreates the "
                f"built-in {match} section"
            )

    if collisions:
        return False, "Duplicates Infrahub's built-in menu: " + "; ".join(
            sorted(set(collisions))
        )
    return True, f"None of the {len(all_items)} items duplicate a built-in section"


def check_parent_attaches_to_builtin(doc: dict, **_: Any) -> tuple[bool, str]:
    """IPAM-domain items reach the shipped IPAM section via parent: BuiltinIPAM."""
    target = "BuiltinIPAM"
    expected_kinds = {"ipamvlan", "ipamvrf"}

    all_items = _all_menu_items_recursive(doc)
    if not all_items:
        return False, "No menu items found"

    attached: list[dict] = []
    for item in all_items:
        if _parent_identifier(item) == target:
            attached.extend(_subtree(item))

    if not attached:
        # Distinguish the three ways this goes wrong, because they need
        # different corrections.
        elsewhere = sorted(
            {p for p in (_parent_identifier(i) for i in all_items) if p in BUILTIN_MENU_SECTIONS}
        )
        unresolvable = sorted(
            {
                str(i.get("parent"))
                for i in all_items
                if _declares_parent(i) and not _parent_identifier(i)
            }
        )
        if elsewhere:
            detail = f"attaches to {', '.join(elsewhere)} instead"
        elif unresolvable:
            detail = (
                f"parent must be a two-element HFID like [Builtin, IPAM]; "
                f"found {', '.join(unresolvable)}"
            )
        else:
            detail = "no item declares a parent"
        return False, f"No item declares parent: [Builtin, IPAM] — {detail}"

    reached = {_normalized(item.get("kind")) for item in attached}
    missing = sorted(expected_kinds - reached)
    if missing:
        return False, (
            f"Not reachable from {target}: {', '.join(missing)} "
            f"(attached kinds: {', '.join(sorted(k for k in reached if k)) or 'none'})"
        )
    return True, f"{len(expected_kinds)} IPAM-domain kinds attach under {target}"


# ---------------------------------------------------------------------------
# Removing items from a loaded menu
#
# ``infrahubctl menu load`` upserts every item in the file and deletes none
# (SDK v1.23.2 ``infrahub_sdk/ctl/menu.py``, ``spec/object.py:535``), so an
# item dropped from the file stays on the instance until something deletes
# it. The checks below grade the apply steps the model writes next to the
# edited menu: the GraphQL ``CoreMenuItemDelete`` calls and the
# ``infrahubctl object delete CoreMenuItem`` commands in its fenced blocks,
# resolved to ``[namespace, name]`` HFIDs, against the items the task removed.
# ---------------------------------------------------------------------------

# A fence may be indented (under a list item, say); the closer repeats the
# opener's backticks or tildes, so a shorter run inside the body cannot end it.
_FENCE_RE = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<lang>[\w+-]*)[^\n]*\n"
    r"(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)

_GQL_TOKEN_RE = re.compile(
    r'"""(?:.|\n)*?"""'           # block string
    r'|"(?:\\.|[^"\\\n])*"'        # string
    r"|#[^\n]*"                    # comment
    r"|\.\.\."                     # spread
    r"|\$?[_A-Za-z][_0-9A-Za-z]*"  # name or variable
    r"|-?\d+(?:\.\d+)?"            # number
    r"|[{}()\[\]:!=@]"             # punctuator
    r"|[\s,]+"                     # ignored
    r"|."
)

_SHELL_LANGS = frozenset({"bash", "sh", "shell", "zsh", "console", "shell-session"})
_GRAPHQL_LANGS = frozenset({"graphql", "gql"})


def _fences(text: str) -> list[tuple[str, str]]:
    """Every fenced block in document order, as ``(language, body)``."""
    return [
        (m.group("lang").lower(), textwrap.dedent(m.group("body")))
        for m in _FENCE_RE.finditer(text or "")
    ]


def _gql_tokens(source: str) -> list[str]:
    """GraphQL tokens with whitespace, commas and ``#`` comments removed."""
    return [
        tok
        for tok in _GQL_TOKEN_RE.findall(source)
        if not tok.isspace() and not tok.startswith("#") and tok.strip(", \t\r\n")
    ]


class _GqlVar:
    """A ``$variable`` reference inside a GraphQL value."""

    def __init__(self, name: str) -> None:
        self.name = name


class _GqlParser:
    """Just enough of a GraphQL parser to read top-level mutation fields."""

    def __init__(self, tokens: list[str]) -> None:
        self.toks = tokens
        self.i = 0

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self) -> str:
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def expect(self, tok: str) -> None:
        if self.take() != tok:
            raise ValueError(f"expected {tok!r}")

    def skip_balanced(self, open_tok: str, close_tok: str) -> None:
        self.expect(open_tok)
        depth = 1
        while depth:
            tok = self.take()
            if tok == open_tok:
                depth += 1
            elif tok == close_tok:
                depth -= 1

    def value(self) -> Any:
        tok = self.take()
        if tok == "[":
            items = []
            while self.peek() != "]":
                items.append(self.value())
            self.take()
            return items
        if tok == "{":
            obj = {}
            while self.peek() != "}":
                key = self.take()
                self.expect(":")
                obj[key] = self.value()
            self.take()
            return obj
        if tok.startswith("$"):
            return _GqlVar(tok[1:])
        if tok.startswith('"""'):
            return tok[3:-3]
        if tok.startswith('"'):
            try:
                return json.loads(tok)
            except ValueError:
                return tok[1:-1]
        return tok

    def arguments(self) -> dict:
        args: dict = {}
        self.expect("(")
        while self.peek() != ")":
            key = self.take()
            self.expect(":")
            args[key] = self.value()
        self.take()
        return args

    def directives(self) -> None:
        while self.peek() == "@":
            self.take()
            self.take()
            if self.peek() == "(":
                self.skip_balanced("(", ")")

    def selection_set(self) -> list[tuple[str, dict]]:
        """Parse ``{ ... }`` and return its direct fields as ``(name, args)``."""
        fields: list[tuple[str, dict]] = []
        self.expect("{")
        while self.peek() != "}":
            if self.peek() == "...":
                self.take()
                if self.peek() == "on":
                    self.take()
                    self.take()
                elif self.peek() not in ("{", "@"):
                    self.take()  # named fragment spread
                    self.directives()
                    continue
                self.directives()
                self.selection_set()
                continue
            name = self.take()
            if self.peek() == ":":
                self.take()
                name = self.take()  # the field behind the alias
            args = self.arguments() if self.peek() == "(" else {}
            self.directives()
            if self.peek() == "{":
                self.selection_set()
            fields.append((name, args))
        self.take()
        return fields

    def mutation_fields(self) -> list[tuple[str, dict]]:
        """Top-level fields of every ``mutation`` operation in the document."""
        found: list[tuple[str, dict]] = []
        while self.peek() is not None:
            tok = self.take()
            if tok in ("mutation", "query", "subscription", "fragment"):
                while self.peek() not in ("{", "(", "@", None):
                    self.take()  # operation name, or ``Name on Type`` for a fragment
                if self.peek() == "(":
                    self.skip_balanced("(", ")")
                self.directives()
                fields = self.selection_set()
                if tok == "mutation":
                    found.extend(fields)
            elif tok == "{":
                self.i -= 1
                self.selection_set()  # anonymous query
        return found


def _resolve(value: Any, variables: dict) -> Any:
    """Substitute ``$variable`` references, recursively."""
    if isinstance(value, _GqlVar):
        return variables.get(value.name)
    if isinstance(value, list):
        return [_resolve(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, variables) for k, v in value.items()}
    return value


def _json_variables(text: str) -> dict:
    """Variables from every ``json`` fence: a bare object, or its ``variables`` key."""
    variables: dict = {}
    for lang, body in _fences(text):
        if lang != "json":
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        if isinstance(data, dict):
            inner = data.get("variables")
            variables.update(inner if isinstance(inner, dict) else data)
    return variables


_CURL_DATA_FLAGS = frozenset({"-d", "--data", "--data-raw", "--data-binary", "--json"})


def _shell_commands(body: str) -> list[list[str]]:
    """Each command line of a shell fence, split with ``shlex``, prompts dropped."""
    commands: list[list[str]] = []
    for line in _expand_for_loops(body.replace("\\\n", " ")).splitlines():
        try:
            words = shlex.split(line, comments=True)
        except ValueError:
            continue
        words = [w for w in words if w != "$"]
        if words:
            commands.append(words)
    return commands


def _request_body(raw: str) -> tuple[str, dict] | None:
    """``(query, variables)`` from a JSON GraphQL request body, if it is one."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if isinstance(data, dict) and isinstance(data.get("query"), str):
        variables = data.get("variables")
        return data["query"], variables if isinstance(variables, dict) else {}
    return None


def _graphql_documents(text: str) -> list[tuple[int, str, dict, bool]]:
    """Every GraphQL document in the fences of ``text``, in document order.

    Returns ``(fence_index, document, variables, declared)`` for ``graphql`` /
    ``gql`` fences, untagged fences, JSON request bodies, and the ``-d`` /
    ``--data*`` / ``--json`` payload of a ``curl`` in a shell fence.
    ``declared`` is false for an untagged fence, which may hold anything.
    """
    documents: list[tuple[int, str, dict, bool]] = []
    for index, (lang, body) in enumerate(_fences(text)):
        if lang in _GRAPHQL_LANGS:
            documents.append((index, body, {}, True))
        elif lang == "":
            documents.append((index, body, {}, False))
        elif lang == "json":
            request = _request_body(body)
            if request:
                documents.append((index, request[0], request[1], True))
        elif lang in _SHELL_LANGS:
            for words in _shell_commands(body):
                for pos, word in enumerate(words):
                    payload = None
                    if word in _CURL_DATA_FLAGS and pos + 1 < len(words):
                        payload = words[pos + 1]
                    elif "=" in word and word.split("=", 1)[0] in _CURL_DATA_FLAGS:
                        payload = word.split("=", 1)[1]
                    request = _request_body(payload) if payload else None
                    if request:
                        documents.append((index, request[0], request[1], True))
    return documents


_TEMPLATE_CHARS = frozenset("<>{}")

Hfid = tuple[str, str]


def _classify_target(identifier: str, known_ids: frozenset[Hfid]) -> tuple[str, list[Hfid]]:
    """Sort a delete target into ``hfid``, ``template`` or ``unresolved``.

    - ``hfid``: two literal parts, the one form that names an item.
    - ``template``: a ``<placeholder>`` or ``{}``. It names no item the grader
      can confirm, so it never satisfies a required delete; but one that spells
      a known item's name (``<WirelessMenu-id>``) still counts as deleting it.
      A placeholder naming nothing known (``Campus/<ChildName>``) is ignored.
    - ``unresolved``: a ``$variable`` left after loop expansion, a UUID, or a
      one-part name. The grader cannot tell what it deletes.
    """
    if "$" in identifier:
        return "unresolved", []
    if _TEMPLATE_CHARS & set(identifier):
        return "template", sorted(h for h in known_ids if h[1] in identifier)
    parts = identifier.split("/")
    if len(parts) == 2 and all(parts):
        return "hfid", [(parts[0], parts[1])]
    return "unresolved", []


_FOR_LOOP_RE = re.compile(
    r"\bfor[ \t]+(?P<var>\w+)[ \t]+in[ \t]+(?P<values>[^;\n]*?)[ \t]*[;\n]\s*do\b"
    r"(?P<body>.*?)[;\n]\s*done\b",
    re.DOTALL,
)


def _expand_for_loops(body: str) -> str:
    """Unroll ``for VAR in a b; do ... $VAR ...; done`` into one command per value."""

    def unroll(match: re.Match) -> str:
        var = match.group("var")
        try:
            values = shlex.split(match.group("values"))
        except ValueError:
            return match.group(0)
        loop_body = match.group("body").strip()
        return "\n".join(
            re.sub(rf"\$\{{{var}\}}|\${var}\b", value, loop_body) for value in values
        )

    return _FOR_LOOP_RE.sub(unroll, body)


def _git_pushes(text: str) -> bool:
    """Whether a shell or untagged fence runs ``git ... push``."""
    separators = {"&&", "||", ";", "|"}
    for lang, body in _fences(text):
        if lang not in _SHELL_LANGS and lang != "":
            continue
        for words in _shell_commands(body):
            for pos, word in enumerate(words):
                if Path(word).name != "git":
                    continue
                for arg in words[pos + 1 :]:
                    if arg in separators:
                        break
                    if arg.rstrip(";") == "push":
                        return True
                    if arg.endswith(";"):
                        break
    return False


_CTL_VALUE_OPTIONS = frozenset({"--branch", "-b", "--config-file"})


def _ctl_object_deletes(
    text: str, known_ids: frozenset[Hfid] = frozenset()
) -> tuple[list[tuple[int, Hfid]], list[str], list[tuple[int, Hfid]]]:
    """``infrahubctl object delete CoreMenuItem <namespace>/<name>`` in shell fences.

    ``object delete`` (SDK 1.20.0+) takes the kind and an identifier, and
    resolves an identifier written with ``/`` as a multi-part HFID. Returns
    ``(deletes, unresolved, template_hits)``, as classified by
    ``_classify_target``.
    """
    deletes: list[tuple[int, Hfid]] = []
    unresolved: list[str] = []
    template_hits: list[tuple[int, Hfid]] = []
    for index, (lang, body) in enumerate(_fences(text)):
        if lang not in _SHELL_LANGS and lang != "":
            continue
        for words in _shell_commands(body):
            for pos, word in enumerate(words[:-2]):
                if Path(word).name != "infrahubctl" or words[pos + 1 : pos + 3] != ["object", "delete"]:
                    continue
                positional: list[str] = []
                rest = iter(words[pos + 3 :])
                for arg in rest:
                    if arg in _CTL_VALUE_OPTIONS:
                        next(rest, None)
                    elif not arg.startswith("-"):
                        positional.append(arg)
                if len(positional) < 2 or positional[0] != "CoreMenuItem":
                    continue
                kind, hfids = _classify_target(positional[1], known_ids)
                if kind == "hfid":
                    deletes.extend((index, h) for h in hfids)
                elif kind == "template":
                    template_hits.extend((index, h) for h in hfids)
                else:
                    unresolved.append(f"infrahubctl object delete CoreMenuItem {positional[1]}")
    return deletes, unresolved, template_hits


def _menu_item_deletes(
    text: str, known_ids: frozenset[Hfid] = frozenset()
) -> tuple[list[tuple[int, Hfid]], list[str], list[tuple[int, Hfid]]]:
    """Menu item deletes in ``text``: GraphQL ``CoreMenuItemDelete`` calls and
    ``infrahubctl object delete CoreMenuItem`` commands.

    Returns ``(deletes, unresolved, template_hits)``: each delete is
    ``(fence_index, (namespace, name))`` for a target written as a literal
    two-part HFID; ``unresolved`` describes targets the grader cannot tie to
    an item (an ``id``, a variable nobody defined); ``template_hits`` are
    placeholders that spell a known item's name. See ``_classify_target``.
    """
    shared_variables = _json_variables(text)
    deletes, unresolved, template_hits = _ctl_object_deletes(text, known_ids)
    for index, document, own_variables, declared in _graphql_documents(text):
        variables = {**shared_variables, **own_variables}
        try:
            fields = _GqlParser(_gql_tokens(document)).mutation_fields()
        except (IndexError, ValueError):
            if declared:
                unresolved.append(f"unparseable GraphQL in fence {index + 1}")
            continue
        for name, args in fields:
            if name != "CoreMenuItemDelete":
                continue
            data = _resolve(args.get("data"), variables)
            hfid = data.get("hfid") if isinstance(data, dict) else None
            if isinstance(hfid, list) and len(hfid) == 2 and all(isinstance(p, str) for p in hfid):
                kind, hfids = _classify_target("/".join(hfid), known_ids)
            else:
                kind, hfids = "unresolved", []
            if kind == "hfid":
                deletes.extend((index, h) for h in hfids)
            elif kind == "template":
                template_hits.extend((index, h) for h in hfids)
            else:
                unresolved.append(f"CoreMenuItemDelete with data={data!r}")
    return deletes, unresolved, template_hits


def _menu_load_fences(text: str) -> list[int]:
    """Indices of shell fences that run ``infrahubctl menu load``."""
    indices: list[int] = []
    for index, (lang, body) in enumerate(_fences(text)):
        if lang not in _SHELL_LANGS and lang != "":
            continue
        for words in _shell_commands(body):
            for pos, word in enumerate(words[:-2]):
                if Path(word).name == "infrahubctl" and words[pos + 1 : pos + 3] == ["menu", "load"]:
                    indices.append(index)
                    break
    return indices


def _hfid_label(hfid: tuple[str, str]) -> str:
    return f"[{hfid[0]}, {hfid[1]}]"


def check_removed_items_dropped(
    doc: dict,
    removed_ids: frozenset[tuple[str, str]] = frozenset(),
    kept_ids: frozenset[tuple[str, str]] = frozenset(),
    **_: Any,
) -> tuple[bool, str]:
    """The edited menu omits every removed item and keeps every other one."""
    present = {
        (str(item.get("namespace") or ""), str(item.get("name") or ""))
        for item in _all_menu_items_recursive(doc)
    }
    still_there = sorted(removed_ids & present)
    if still_there:
        return False, "Removed items still in the menu file: " + ", ".join(
            _hfid_label(h) for h in still_there
        )
    lost = sorted(kept_ids - present)
    if lost:
        return False, "Items that should stay are missing from the menu file: " + ", ".join(
            _hfid_label(h) for h in lost
        )
    return True, f"{len(removed_ids)} items dropped, {len(kept_ids)} kept"


def check_removed_items_deleted(
    doc: dict,
    apply_raw: str = "",
    removed_ids: frozenset[tuple[str, str]] = frozenset(),
    kept_ids: frozenset[tuple[str, str]] = frozenset(),
    hand_delete_ids: frozenset[tuple[str, str]] | None = None,
    sync_removed_ids: frozenset[tuple[str, str]] = frozenset(),
    **_: Any,
) -> tuple[bool, str]:
    """The apply steps delete by hand exactly the items nothing else removes.

    ``infrahubctl menu load`` never deletes, so after a CLI load each removed
    item, group header and children alike (a header delete does not cascade),
    needs its own delete: ``hand_delete_ids`` defaults to ``removed_ids``.
    A git-synced ``menus:`` file is reconciled by the sync, which deletes the
    items it loaded before and no longer finds (Infrahub 1.3.0+), so those
    (``sync_removed_ids``) must not be deleted by hand, the change must be
    pushed so a sync runs at all, and an item loaded outside the sync still
    needs a delete. A purge of kept items is allowed only when a
    later ``infrahubctl menu load`` puts them back; ``Builtin`` items are
    protected and a delete of one is refused.
    """
    must_delete = removed_ids if hand_delete_ids is None else hand_delete_ids
    known_ids = removed_ids | kept_ids | must_delete | sync_removed_ids
    deletes, unresolved, template_hits = _menu_item_deletes(apply_raw, known_ids)
    targets = {hfid for _, hfid in deletes}
    # A placeholder spelling a known item counts against the answer, never for it.
    touched = deletes + template_hits
    touched_ids = {hfid for _, hfid in touched}

    builtin = sorted(h for h in targets if h[0] == "Builtin")
    if builtin:
        return False, "Deletes protected built-in items: " + ", ".join(
            _hfid_label(h) for h in builtin
        )

    loads = _menu_load_fences(apply_raw)
    not_reloaded = sorted(
        {hfid for index, hfid in touched if hfid in kept_ids and not any(load > index for load in loads)}
    )
    if not_reloaded:
        return False, (
            "Deletes items the new menu keeps, with no later infrahubctl menu load "
            "to restore them: " + ", ".join(_hfid_label(h) for h in not_reloaded)
        )

    by_hand = sorted(touched_ids & sync_removed_ids)
    if by_hand:
        return False, (
            "Deletes by hand items the git sync removes on its own: "
            + ", ".join(_hfid_label(h) for h in by_hand)
        )

    if sync_removed_ids and not _git_pushes(apply_raw):
        return False, (
            "No git push of the menu change: without it no sync runs, and the "
            "items dropped from the file stay in the sidebar"
        )

    missing = sorted(must_delete - targets)
    if sync_removed_ids and len(unresolved) > len(missing):
        # A delete by UUID or placeholder cannot be tied to an item. More of
        # them than items still needing a delete means at least one lands on
        # an item the sync owns or the menu keeps.
        return False, (
            f"{len(unresolved)} deletes by an identifier that is not a "
            f"[namespace, name] HFID, but only {len(missing)} item(s) outside the "
            "sync need one: " + "; ".join(unresolved)
        )
    if missing:
        detail = f"; unresolved deletes: {'; '.join(unresolved)}" if unresolved else ""
        return False, (
            "No delete for items that nothing else removes (a menu load never deletes): "
            + ", ".join(_hfid_label(h) for h in missing)
            + detail
        )
    return True, f"Every item needing a delete ({len(must_delete)}) is deleted from the instance"


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "apiversion-and-kind": check_apiversion_and_kind,
    "spec-data-structure": check_spec_data_structure,
    "name-and-namespace": check_name_and_namespace,
    "kind-for-schema-links": check_kind_for_schema_links,
    "mdi-icons": check_mdi_icons,
    "labels-present": check_labels_present,
    "group-headers-no-kind": check_group_headers_no_kind,
    "children-data-wrapper": check_children_data_wrapper,
    "leaf-items-have-kind": check_leaf_items_have_kind,
    "correct-grouping": check_correct_grouping,
    "all-nodes-present": check_all_nodes_present,
    "contextual-icons": check_contextual_icons,
    "generic-kind-link": check_generic_kind_link,
    "location-children": check_location_children,
    "separate-devices-section": check_separate_devices_section,
    "include-in-menu-false": check_include_in_menu_false,
    "infrahub-yml-registration": check_infrahub_yml_registration,
    "schema-comment": check_schema_comment,
    "no-builtin-section-recreated": check_no_builtin_section_recreated,
    "parent-attaches-to-builtin": check_parent_attaches_to_builtin,
    "removed-items-dropped": check_removed_items_dropped,
    "removed-items-deleted": check_removed_items_deleted,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_path: Path,
    raw_text: str | None = None,
    apply_path: Path | None = None,
    **check_kwargs: Any,
) -> dict:
    """Run named checks against a menu YAML file and return skillgrade JSON.

    Parameters
    ----------
    check_names:
        List of assertion names from the ``CHECKS`` registry.
    output_path:
        Path to the menu YAML file produced by the model.
    raw_text:
        Optional pre-loaded raw text (used by checks that inspect comments).
        If ``None``, the file is read from ``output_path``.
    apply_path:
        Optional Markdown file of apply steps, passed to checks as
        ``apply_raw`` (empty when absent).
    check_kwargs:
        Task inputs forwarded to every check, e.g. ``removed_ids``.

    Returns
    -------
    dict with keys:
        - ``score`` (float 0.0-1.0)
        - ``details`` (str summary)
        - ``checks`` (list of ``{"name", "passed", "message"}``)

    Raises
    ------
    KeyError
        If any name in ``check_names`` is not in ``CHECKS``.
    """
    doc, file_raw = load_output(output_path)
    if raw_text is None:
        raw_text = file_raw
    apply_raw = ""
    if apply_path is not None:
        try:
            apply_raw = Path(apply_path).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            apply_raw = ""

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            ok, msg = fn(doc, raw_text=raw_text, apply_raw=apply_raw, **check_kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"

        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0

    failed_names = [e["name"] for e in entries if not e["passed"]]
    if failed_names:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed_names)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}
