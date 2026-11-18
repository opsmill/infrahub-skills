"""Grader library for the infrahub-building-sync-adapters skill.

Every check parses its artifact: YAML through ``yaml.safe_load``, Python
through ``ast``, Markdown by locating a section and tokenizing its commands
with ``shlex``. The expected API facts are derived from the ServiceNow
captures under ``data/servicenow/``, taken from a real instance, so the
graders hold no second copy of them.

The strict-fake checks execute the model's fake in a subprocess with network
access blocked and a timeout (``_fake_probe.py``), because what a fake does
with a request is only observable by sending it one.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import yaml

_HERE = Path(__file__).resolve().parent
DATA = _HERE / "data" / "servicenow"

# --------------------------------------------------------------------------
# Captures
# --------------------------------------------------------------------------


def load_captures() -> list[dict]:
    """Return every captured response, each with ``request``, ``status``, ``headers``, ``body``."""
    return [json.loads(p.read_text()) for p in sorted(DATA.glob("*.json"))]


def endpoint_path(url_or_path: str) -> str:
    """Return the URL path without query, for a full URL or a bare path."""
    return urlsplit(url_or_path).path.rstrip("/")


def parse_link_header(value: str) -> dict[str, str]:
    """Map each ``rel`` to its URL. Selects rels exactly, so ``prev`` never stands in for ``next``."""
    return {
        rel: url
        for url, rel in re.findall(r'<([^>]*)>\s*;\s*rel="([^"]+)"', value or "")
    }


def _header(headers: dict, name: str) -> str | None:
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return value
    return None


def captured_endpoints() -> dict[str, dict]:
    """Facts per endpoint path, derived from the captures."""
    facts: dict[str, dict] = {}
    for cap in load_captures():
        path = endpoint_path(cap["request"]["path"])
        entry = facts.setdefault(
            path,
            {
                "next_params": set(),
                "rate_limited": False,
                "reference_set": False,
                "reference_empty": False,
                "dropped_fields": set(),
            },
        )
        if cap["status"] == 429:
            entry["rate_limited"] = True
            continue
        nxt = parse_link_header(_header(cap["headers"], "Link") or "").get("next")
        if nxt:
            entry["next_params"] |= {k for k, _ in parse_qsl(urlsplit(nxt).query)} - {
                "sysparm_offset"
            }
        requested = dict(parse_qsl(urlsplit(cap["request"]["path"]).query)).get(
            "sysparm_fields"
        )
        rows = cap["body"].get("result", []) if isinstance(cap["body"], dict) else []
        returned = set().union(*(r.keys() for r in rows)) if rows else set()
        if requested and rows:
            entry["dropped_fields"] |= {f for f in requested.split(",") if f} - returned
        for row in rows:
            for value in row.values():
                if isinstance(value, dict) and {"link", "value"} <= value.keys():
                    entry["reference_set"] = True
        # an empty reference is "" for a field that is an object in another row
        ref_fields = {k for r in rows for k, v in r.items() if isinstance(v, dict)}
        if any(r.get(k) == "" for r in rows for k in ref_fields):
            entry["reference_empty"] = True
    return facts


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def load_yaml_file(path: Path) -> tuple[Any, str]:
    """Parse a YAML file; accept an answer whose YAML sits in fenced blocks."""
    if not path.exists():
        return None, f"{path} not found"
    raw = path.read_text()
    for candidate in [raw, *_FENCE.findall(raw)]:
        try:
            data = yaml.safe_load(candidate)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            return data, ""
    return None, f"{path} does not parse as a YAML mapping"


def load_python(path: Path) -> tuple[ast.Module | None, str]:
    if not path.exists():
        return None, f"{path} not found"
    raw = path.read_text()
    blocks = _FENCE.findall(raw)
    for candidate in [raw, *blocks]:
        try:
            return ast.parse(candidate), ""
        except SyntaxError:
            continue
    return None, f"{path} is not valid Python"


# --------------------------------------------------------------------------
# Task 1: API behavior file
# --------------------------------------------------------------------------

BEHAVIOR_KEYS = (
    "path",
    "method",
    "pagination",
    "required_headers",
    "default_fields",
    "field_selection",
    "filters_supported",
    "rate_limit",
    "empty_result_is_valid",
    "captures",
    "field_quirks",
    "subclass_rows",
)


def _behavior_entries(doc: Any) -> list[dict]:
    if not isinstance(doc, dict) or not isinstance(doc.get("endpoints"), list):
        return []
    return [e for e in doc["endpoints"] if isinstance(e, dict)]


def _entry_for(entries: list[dict], path: str) -> dict | None:
    for entry in entries:
        if isinstance(entry.get("path"), str) and endpoint_path(entry["path"]).endswith(
            path
        ):
            return entry
    return None


def check_behavior_keys(ctx: dict) -> tuple[bool, str]:
    """Every endpoint entry carries the fixed key set."""
    entries = _behavior_entries(ctx["behavior"])
    if not entries:
        return False, "behavior-keys: no `endpoints` list in api-behavior.yml"
    gaps = {
        e.get("path", "?"): [k for k in BEHAVIOR_KEYS if k not in e] for e in entries
    }
    gaps = {p: ks for p, ks in gaps.items() if ks}
    if gaps:
        return False, f"behavior-keys: entries missing keys: {gaps}"
    return True, "behavior-keys: every entry has the fixed key set"


def check_behavior_covers_endpoints(ctx: dict) -> tuple[bool, str]:
    """Every captured endpoint has an entry."""
    entries = _behavior_entries(ctx["behavior"])
    missing = [p for p in captured_endpoints() if _entry_for(entries, p) is None]
    if missing:
        return (
            False,
            f"behavior-covers-endpoints: no entry for captured endpoints {missing}",
        )
    return True, "behavior-covers-endpoints: every captured endpoint has an entry"


def check_behavior_next_link(ctx: dict) -> tuple[bool, str]:
    """`pagination.next_link_carries` lists the parameters the captured next link repeats."""
    entries = _behavior_entries(ctx["behavior"])
    problems = []
    for path, facts in captured_endpoints().items():
        if not facts["next_params"]:
            continue
        entry = _entry_for(entries, path) or {}
        pag = (
            entry.get("pagination") if isinstance(entry.get("pagination"), dict) else {}
        )
        carries = pag.get("next_link_carries") or []
        carries = {str(c) for c in carries} if isinstance(carries, list) else set()
        lacking = facts["next_params"] - carries
        if lacking:
            problems.append(f"{path} lacks {sorted(lacking)}")
    if problems:
        return (
            False,
            "behavior-next-link: next_link_carries does not match the captured next link: "
            + "; ".join(problems),
        )
    return True, "behavior-next-link: next_link_carries matches the captured next links"


def check_behavior_rate_limit(ctx: dict) -> tuple[bool, str]:
    """Endpoints with a captured 429 record status 429 and a Retry-After header."""
    entries = _behavior_entries(ctx["behavior"])
    problems = []
    for path, facts in captured_endpoints().items():
        if not facts["rate_limited"]:
            continue
        rl = (_entry_for(entries, path) or {}).get("rate_limit")
        if (
            not isinstance(rl, dict)
            or rl.get("status") != 429
            or rl.get("retry_after_header") is not True
        ):
            problems.append(path)
    if problems:
        return (
            False,
            f"behavior-rate-limit: rate_limit does not record the captured 429 with Retry-After for {problems}",
        )
    return True, "behavior-rate-limit: captured 429 recorded"


def check_behavior_field_quirks(ctx: dict) -> tuple[bool, str]:
    """`field_quirks` records the reference shapes and silently dropped fields the captures show."""
    entries = _behavior_entries(ctx["behavior"])
    problems = []
    for path, facts in captured_endpoints().items():
        entry = _entry_for(entries, path)
        if entry is None:
            # A missing entry records no quirk; passing here would be vacuous.
            problems.append(f"{path}: no entry")
            continue
        quirks = (
            entry.get("field_quirks")
            if isinstance(entry.get("field_quirks"), dict)
            else {}
        )
        if facts["reference_set"] and quirks.get("reference_set") != "object":
            problems.append(f"{path}: reference_set should be object")
        if facts["reference_empty"] and quirks.get("reference_empty") != "empty_string":
            problems.append(f"{path}: reference_empty should be empty_string")
        if (
            facts["dropped_fields"]
            and quirks.get("unknown_selected_field") != "dropped_silently"
        ):
            problems.append(
                f"{path}: unknown_selected_field should be dropped_silently"
            )
    if problems:
        return False, "behavior-field-quirks: " + "; ".join(problems)
    return True, "behavior-field-quirks: reference shapes and dropped fields recorded"


# --------------------------------------------------------------------------
# Task 2: strict fake
# --------------------------------------------------------------------------


def run_fake_probe(output_dir: Path) -> dict:
    """Run ``_fake_probe.py`` against the model's fake; return its JSON report."""
    if not output_dir.is_dir():
        return {"error": f"no {output_dir}/ directory: the fake was not written there"}
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-I",
                str(_HERE / "_fake_probe.py"),
                str(output_dir.resolve()),
                str(DATA),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(output_dir.resolve()),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": "probe timed out after 60 s"}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"error": f"probe crashed: {proc.stderr.strip()[-400:]}"}


def _probe(ctx: dict) -> dict:
    if "probe" not in ctx:
        ctx["probe"] = run_fake_probe(ctx["output_dir"])
    return ctx["probe"]


def _scenario(ctx: dict, name: str) -> tuple[dict | None, str]:
    probe = _probe(ctx)
    if probe.get("error"):
        return None, probe["error"]
    sc = probe.get(name) or {}
    if sc.get("error"):
        return None, sc["error"]
    return sc, ""


def _captured_rows(table: str) -> dict[str, dict]:
    """The rows captured from one table, keyed by sys_id."""
    rows: dict[str, dict] = {}
    for cap in load_captures():
        if endpoint_path(cap["request"]["path"]).rsplit("/", 1)[-1] != table:
            continue
        if isinstance(cap["body"], dict):
            for r in cap["body"].get("result", []):
                if isinstance(r, dict) and r.get("sys_id"):
                    rows[r["sys_id"]] = r
    return rows


# The "selected" scenario of _fake_probe.py asks cmdb_ci_netgear for these fields.
_SELECTED_FIELDS = ("sys_id", "name")


def check_fake_serves_captures(ctx: dict) -> tuple[bool, str]:
    """Every row the fake returns is a captured row, with the captured values."""
    sc, err = _scenario(ctx, "selected")
    if sc is None:
        return False, f"fake-serves-captures: {err}"
    if not sc["rows"]:
        return False, "fake-serves-captures: the fake returned no rows"
    captured = _captured_rows("cmdb_ci_netgear")
    problems = []
    for row in sc["rows"]:
        source = captured.get(row.get("sys_id"))
        if source is None:
            problems.append(f"sys_id {row.get('sys_id')!r} is not in the captures")
            continue
        for field in _SELECTED_FIELDS:
            if field in row and row[field] != source.get(field):
                problems.append(
                    f"{row['sys_id']}: {field}={row[field]!r}, captured {source.get(field)!r}"
                )
    if problems:
        return (
            False,
            "fake-serves-captures: rows differ from the captures: "
            + "; ".join(problems[:4]),
        )
    return True, "fake-serves-captures: every row matches a captured row"


def check_fake_field_selection(ctx: dict) -> tuple[bool, str]:
    """A request with sysparm_fields gets only those fields back."""
    sc, err = _scenario(ctx, "selected")
    if sc is None:
        return False, f"fake-field-selection: {err}"
    extra = (
        set().union(*(set(r) for r in sc["rows"])) - set(_SELECTED_FIELDS)
        if sc["rows"]
        else set()
    )
    if not sc["rows"] or extra:
        return (
            False,
            f"fake-field-selection: asked for sys_id,name and got extra fields {sorted(extra)[:8]} (rows={len(sc['rows'])})",
        )
    return True, "fake-field-selection: only the selected fields are returned"


def check_fake_drops_unknown(ctx: dict) -> tuple[bool, str]:
    """A field the table lacks is dropped silently with HTTP 200, as the real API does."""
    sc, err = _scenario(ctx, "unknown_field")
    if sc is None:
        return False, f"fake-drops-unknown: {err}"
    if sc["status"] != 200:
        return (
            False,
            f"fake-drops-unknown: unknown field returned HTTP {sc['status']}; the real API returns 200",
        )
    keys = set().union(*(set(r) for r in sc["rows"])) if sc["rows"] else set()
    if not sc["rows"] or keys != {"sys_id"}:
        return (
            False,
            f"fake-drops-unknown: expected rows with only sys_id, got keys {sorted(keys)}",
        )
    return True, "fake-drops-unknown: unknown field dropped silently"


def check_fake_reference_shapes(ctx: dict) -> tuple[bool, str]:
    """References come back as {link, value} when set and "" when empty."""
    sc, err = _scenario(ctx, "references")
    if sc is None:
        return False, f"fake-reference-shapes: {err}"
    values = [r.get("location") for r in sc["rows"]]
    has_obj = any(isinstance(v, dict) and {"link", "value"} <= v.keys() for v in values)
    has_empty = any(v == "" for v in values)
    if not (has_obj and has_empty):
        return (
            False,
            f"fake-reference-shapes: location values {values[:4]} lack an object or an empty string",
        )
    return True, "fake-reference-shapes: object when set, empty string when empty"


def check_fake_next_link(ctx: dict) -> tuple[bool, str]:
    """The captured page's next link is served exactly as captured."""
    sc, err = _scenario(ctx, "captured_page")
    if sc is None:
        return False, f"fake-next-link: {err}"
    if sc.get("next") != sc.get("expected_next"):
        return (
            False,
            f"fake-next-link: next link {sc.get('next')!r} differs from the captured {sc.get('expected_next')!r}",
        )
    return True, "fake-next-link: next link served as captured"


# --------------------------------------------------------------------------
# Task 3: PR check list
# --------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_SECTION_WORDS = re.compile(r"check|test|verif|validat|gate", re.IGNORECASE)
_CODE = re.compile(r"```[^\n]*\n(.*?)```|`([^`\n]+)`", re.DOTALL)


def _checks_section(text: str) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and _SECTION_WORDS.search(m.group(2)):
            level = len(m.group(1))
            body = []
            for nxt in lines[i + 1 :]:
                n = _HEADING.match(nxt)
                if n and len(n.group(1)) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return None


def _command_tokens(section: str) -> list[list[str]]:
    out = []
    for fenced, inline in _CODE.findall(section):
        for line in (fenced or inline).splitlines():
            line = line.strip().lstrip("$ ").strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(shlex.split(line))
            except ValueError:
                out.append(line.split())
    return out


def _has_seq(tokens: list[str], seq: list[str]) -> bool:
    return any(tokens[i : i + len(seq)] == seq for i in range(len(tokens)))


PR_ITEMS: dict[str, Callable[[list[str]], bool]] = {
    "format": lambda t: _has_seq(t, ["invoke", "format"]),
    "lint": lambda t: _has_seq(t, ["invoke", "lint"]),
    "type check": lambda t: _has_seq(t, ["ty", "check"]),
    "unit tests": lambda t: (
        "pytest" in t
        or any(x.startswith("tests.") for x in t)
        or _has_seq(t, ["invoke", "tests"])
    ),
    "markdown lint": lambda t: "rumdl" in t,
    "docs build": lambda t: (
        any(x.startswith("docs.") for x in t)
        or "docusaurus" in t
        or _has_seq(t, ["npm", "run", "build"])
    ),
    "infrahub-sync list": lambda t: _has_seq(t, ["infrahub-sync", "list"]),
    "infrahub-sync generate": lambda t: _has_seq(t, ["infrahub-sync", "generate"]),
    "infrahub-sync diff": lambda t: _has_seq(t, ["infrahub-sync", "diff"]),
    "news fragment": lambda t: (
        "towncrier" in t or any(re.match(r"^changelog/.+\.md$", x) for x in t)
    ),
    "docs page": lambda t: any(
        re.match(r"^docs/docs/adapters/[^/]+\.mdx$", x)
        and not x.endswith("choosing-an-adapter.mdx")
        for x in t
    ),
    "docs sidebar": lambda t: any(x.endswith("sidebars.ts") for x in t),
    "choosing-an-adapter row": lambda t: any(
        x.endswith("choosing-an-adapter.mdx") for x in t
    ),
    "spec documents": lambda t: any("specs/" in x for x in t),
}


def check_pr_checks_complete(ctx: dict) -> tuple[bool, str]:
    """The PR's checks section names every required check."""
    text = ctx["pr_text"]
    if text is None:
        return False, "pr-checks-complete: PR_DESCRIPTION.md not found"
    section = _checks_section(text)
    if section is None:
        return (
            False,
            "pr-checks-complete: no checks section (a heading naming checks, tests, verification or validation)",
        )
    commands = _command_tokens(section)
    missing = [
        name for name, hit in PR_ITEMS.items() if not any(hit(t) for t in commands)
    ]
    if missing:
        return False, f"pr-checks-complete: the checks section omits {missing}"
    return True, "pr-checks-complete: every required check is listed"


# --------------------------------------------------------------------------
# Task 4: retry policy (AST)
# --------------------------------------------------------------------------

RETRY_STATUSES = {429, 502, 503, 504}


def _strip_docstrings(tree: ast.Module) -> ast.Module:
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return tree


def _numeric_names(tree: ast.Module) -> dict[str, float]:
    """Names bound once to a number literal, at any level (module constants, class attributes)."""
    names: dict[str, float] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if (
                isinstance(value, ast.Constant)
                and isinstance(value.value, (int, float))
                and not isinstance(value.value, bool)
            ):
                for t in targets:
                    name = (
                        t.id
                        if isinstance(t, ast.Name)
                        else t.attr
                        if isinstance(t, ast.Attribute)
                        else None
                    )
                    if name:
                        names[name] = value.value
    return names


def _num(node: ast.AST, names: dict[str, float]) -> float | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.Attribute):
        return names.get(node.attr)
    return None


def _collection_ints(node: ast.AST, names: dict[str, float]) -> set[int] | None:
    """The integers of a literal collection, or of ``frozenset({...})`` / ``set([...])``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("frozenset", "set", "tuple", "list")
        and len(node.args) == 1
    ):
        node = node.args[0]
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)) and node.elts:
        vals = [_num(e, names) for e in node.elts]
        if all(v is not None for v in vals):
            return {int(v) for v in vals}
    return None


def _named_collections(
    tree: ast.Module, names: dict[str, float]
) -> dict[str, set[int]]:
    """Names (module constants, attributes) bound to a collection of integers."""
    out: dict[str, set[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            ints = _collection_ints(node.value, names)
            if ints is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    out[t.id] = ints
                elif isinstance(t, ast.Attribute):
                    out[t.attr] = ints
    return out


def _mentions_status(node: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Name) and "status" in n.id.lower())
        or (isinstance(n, ast.Attribute) and "status" in n.attr.lower())
        for n in ast.walk(node)
    )


def check_retry_status_set(ctx: dict) -> tuple[bool, str]:
    """The response status is tested for membership in exactly {429, 502, 503, 504}."""
    tree = ctx["py"]
    if tree is None:
        return False, f"retry-status-set: {ctx['py_err']}"
    names = _numeric_names(tree)
    named = _named_collections(tree, names)
    tested: list[list[int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or not _mentions_status(node.left):
            continue
        for op, comp in zip(node.ops, node.comparators):
            if not isinstance(op, (ast.In, ast.NotIn)):
                continue
            ints = _collection_ints(comp, names)
            if ints is None and isinstance(comp, (ast.Name, ast.Attribute)):
                ints = named.get(comp.id if isinstance(comp, ast.Name) else comp.attr)
            if ints is None:
                continue
            if ints == RETRY_STATUSES:
                return (
                    True,
                    "retry-status-set: the response status is tested against 429, 502, 503, 504",
                )
            tested.append(sorted(ints))
    return (
        False,
        "retry-status-set: no test of the response status against "
        f"{sorted(RETRY_STATUSES)} (statuses tested: {tested})",
    )


# Data flow inside the client module. Each expression carries labels:
#   retry_after: derived from the Retry-After header
#   jitter:      derived from a random draw
#   capped:      bounded at 60 s, by min(..., 60) or by `if x > 60: x = 60`
# Labels pass through assignments, through any call that takes a labelled
# argument, and through functions whose return value is labelled. The analysis
# ignores statement order inside a function, which is enough for a client of
# this size and errs toward passing a value that is labelled on any branch.

_RANDOM_MODULES = ("random", "secrets")


def _is_retry_after_read(node: ast.AST) -> bool:
    key = None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
    ):
        key = node.args[0]
    elif isinstance(node, ast.Subscript):
        key = node.slice
    return (
        isinstance(key, ast.Constant)
        and isinstance(key.value, str)
        and key.value.lower() == "retry-after"
    )


def _random_names(tree: ast.Module) -> set[str]:
    """Names imported from random or secrets (``from random import uniform``)."""
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in _RANDOM_MODULES
        for alias in node.names
    }


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _scopes(tree: ast.Module) -> list[tuple[str, list[ast.stmt]]]:
    """The module's top-level statements, and each function body, as separate scopes."""
    scopes: list[tuple[str, list[ast.stmt]]] = [
        (
            "<module>",
            [
                s
                for s in tree.body
                if not isinstance(
                    s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
            ],
        )
    ]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append((f"{node.name}@{node.lineno}", node.body))
    return scopes


def _target_names(target: ast.AST) -> list[str]:
    return [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]


class _Flow:
    """Labels on local names and on function return values, solved to a fixed point."""

    def __init__(self, tree: ast.Module) -> None:
        self.names = _numeric_names(tree)
        self.random_names = _random_names(tree)
        self.scopes = _scopes(tree)
        self.var: dict[tuple[str, str], set[str]] = {}
        self.ret: dict[str, set[str]] = {}
        for _ in range(20):
            if not self._step():
                break

    def labels(self, expr: ast.AST, scope: str) -> set[str]:
        out: set[str] = set()
        for n in ast.walk(expr):
            if isinstance(n, ast.Name):
                out |= self.var.get((scope, n.id), set())
            if _is_retry_after_read(n):
                out.add("retry_after")
            if isinstance(n, ast.Call):
                name = _call_name(n.func)
                if (
                    isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id in _RANDOM_MODULES
                ) or (isinstance(n.func, ast.Name) and n.func.id in self.random_names):
                    out.add("jitter")
                if name == "min" and any(_num(a, self.names) == 60 for a in n.args):
                    out.add("capped")
                if name:
                    out |= self.ret.get(name, set())
        return out

    def _add(self, store: dict, key, labels: set[str]) -> bool:
        current = store.setdefault(key, set())
        if labels <= current:
            return False
        current |= labels
        return True

    def _step(self) -> bool:
        changed = False
        for scope, body in self.scopes:
            fname = scope.split("@", 1)[0]
            for stmt in body:
                for n in ast.walk(stmt):
                    if (
                        isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))
                        and n.value is not None
                    ):
                        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                        labels = self.labels(n.value, scope)
                        for t in targets:
                            for name in _target_names(t):
                                changed |= self._add(self.var, (scope, name), labels)
                    elif isinstance(n, ast.NamedExpr):
                        changed |= self._add(
                            self.var, (scope, n.target.id), self.labels(n.value, scope)
                        )
                    elif isinstance(n, ast.If):
                        # `if delay > 60: delay = 60` caps `delay`
                        for name in self._capped_by_if(n):
                            changed |= self._add(self.var, (scope, name), {"capped"})
                    elif (
                        isinstance(n, ast.Return)
                        and n.value is not None
                        and scope != "<module>"
                    ):
                        changed |= self._add(
                            self.ret, fname, self.labels(n.value, scope)
                        )
        return changed

    def _capped_by_if(self, node: ast.If) -> list[str]:
        compared = [
            x.id
            for cmp in ast.walk(node.test)
            if isinstance(cmp, ast.Compare)
            and any(_num(y, self.names) == 60 for y in [cmp.left, *cmp.comparators])
            for x in [cmp.left, *cmp.comparators]
            if isinstance(x, ast.Name)
        ]
        assigned = {
            name
            for stmt in node.body
            for n in ast.walk(stmt)
            if isinstance(n, ast.Assign)
            for t in n.targets
            for name in _target_names(t)
        }
        return [c for c in compared if c in assigned]

    def sleeps(self) -> list[set[str]]:
        """The labels of the argument of every ``sleep(...)`` call."""
        out = []
        for scope, body in self.scopes:
            for stmt in body:
                for n in ast.walk(stmt):
                    if (
                        isinstance(n, ast.Call)
                        and _call_name(n.func) == "sleep"
                        and n.args
                    ):
                        out.append(self.labels(n.args[0], scope))
        return out


def _flow(ctx: dict) -> _Flow:
    if "flow" not in ctx:
        ctx["flow"] = _Flow(ctx["py"])
    return ctx["flow"]


def check_retry_after_honored(ctx: dict) -> tuple[bool, str]:
    """The Retry-After value reaches the wait the client sleeps on."""
    tree = ctx["py"]
    if tree is None:
        return False, f"retry-after-honored: {ctx['py_err']}"
    if not any(_is_retry_after_read(n) for n in ast.walk(tree)):
        return False, "retry-after-honored: the code never reads the Retry-After header"
    if any("retry_after" in labels for labels in _flow(ctx).sleeps()):
        return True, "retry-after-honored: the Retry-After value sets the sleep"
    return (
        False,
        "retry-after-honored: Retry-After is read but no sleep() waits on its value",
    )


def check_retry_after_cap(ctx: dict) -> tuple[bool, str]:
    """A Retry-After wait longer than 300 s raises instead of sleeping."""
    tree = ctx["py"]
    if tree is None:
        return False, f"retry-after-cap: {ctx['py_err']}"
    flow = _flow(ctx)
    for scope, body in flow.scopes:
        for stmt in body:
            for node in ast.walk(stmt):
                if not isinstance(node, ast.If) or not any(
                    isinstance(n, ast.Raise) for s in node.body for n in ast.walk(s)
                ):
                    continue
                for cmp in ast.walk(node.test):
                    if not isinstance(cmp, ast.Compare):
                        continue
                    operands = [cmp.left, *cmp.comparators]
                    if any(_num(x, flow.names) == 300 for x in operands) and any(
                        "retry_after" in flow.labels(x, scope) for x in operands
                    ):
                        return (
                            True,
                            "retry-after-cap: a Retry-After wait over 300 s raises",
                        )
    return (
        False,
        "retry-after-cap: no branch that compares the Retry-After wait with 300 s and raises",
    )


def check_backoff_capped_jitter(ctx: dict) -> tuple[bool, str]:
    """A slept backoff is capped at 60 s and drawn with random jitter."""
    tree = ctx["py"]
    if tree is None:
        return False, f"backoff-capped-jitter: {ctx['py_err']}"
    sleeps = _flow(ctx).sleeps()
    if any({"capped", "jitter"} <= labels for labels in sleeps):
        return (
            True,
            "backoff-capped-jitter: the slept backoff is capped at 60 s with jitter",
        )
    seen = sorted({tuple(sorted(lbl & {"capped", "jitter"})) for lbl in sleeps})
    return (
        False,
        f"backoff-capped-jitter: no sleep() waits on a value both capped at 60 s and jittered (sleeps carry {seen})",
    )


_BROAD = {
    "ConnectionError",
    "RequestException",
    "OSError",
    "Exception",
    "BaseException",
}


def _handler_names(handler: ast.ExceptHandler) -> set[str]:
    t = handler.type
    elts = t.elts if isinstance(t, ast.Tuple) else [t] if t is not None else []
    return {
        e.id if isinstance(e, ast.Name) else e.attr
        for e in elts
        if isinstance(e, (ast.Name, ast.Attribute))
    }


def _reraises(handler: ast.ExceptHandler) -> bool:
    nodes = [n for stmt in handler.body for n in ast.walk(stmt)]
    return any(isinstance(n, ast.Raise) for n in nodes) and not any(
        isinstance(n, ast.Continue) for n in nodes
    )


_HTTP_RECEIVERS = ("session", "client", "http", "requests", "httpx")


def _calls_http(stmts: list[ast.stmt]) -> bool:
    """The statements call an HTTP session or client (``self.session.get(...)``, ``requests.get(...)``)."""
    for stmt in stmts:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                receiver = n.func.value
                name = (
                    receiver.id
                    if isinstance(receiver, ast.Name)
                    else receiver.attr
                    if isinstance(receiver, ast.Attribute)
                    else ""
                )
                if any(word in name.lower() for word in _HTTP_RECEIVERS):
                    return True
    return False


def check_no_tls_retry(ctx: dict) -> tuple[bool, str]:
    """A handler that retries connection errors handles SSLError first, so TLS errors are not retried."""
    tree = ctx["py"]
    if tree is None:
        return False, f"no-tls-retry: {ctx['py_err']}"
    broad_seen = False
    for node in ast.walk(tree):
        # Only the try around the HTTP call retries; an unrelated
        # ``except OSError`` (a reset-time parse, a file read) does not.
        if not isinstance(node, ast.Try) or not _calls_http(node.body):
            continue
        ssl_handled = False
        for handler in node.handlers:
            names = _handler_names(handler)
            if "SSLError" in names:
                # Only a handler that re-raises excludes TLS errors; one that
                # continues or swallows the error still retries them.
                ssl_handled = _reraises(handler)
                continue
            if names & _BROAD:
                broad_seen = True
                isinstance_guard = any(
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "isinstance"
                    and any(
                        isinstance(x, (ast.Name, ast.Attribute))
                        and getattr(x, "id", getattr(x, "attr", "")) == "SSLError"
                        for x in ast.walk(n)
                    )
                    for stmt in handler.body
                    for n in ast.walk(stmt)
                )
                if not (ssl_handled or isinstance_guard):
                    return (
                        False,
                        "no-tls-retry: a handler catching connection errors retries SSLError, which subclasses ConnectionError",
                    )
    if not broad_seen:
        return (
            False,
            "no-tls-retry: no handler retries dropped or timed-out connections",
        )
    return True, "no-tls-retry: connection errors retried, TLS errors excluded"


# --------------------------------------------------------------------------
# Task 5: identifiers match the human-friendly ID
# --------------------------------------------------------------------------


def schema_hfids(schema: dict) -> dict[str, list[str]]:
    """Map each node kind to the fields of its human_friendly_id, inherited from a generic when the node has none."""
    generics = {
        f"{g.get('namespace', '')}{g.get('name', '')}": g.get("human_friendly_id")
        for g in schema.get("generics", []) or []
    }
    out = {}
    for node in schema.get("nodes", []) or []:
        kind = f"{node.get('namespace', '')}{node.get('name', '')}"
        hfid = node.get("human_friendly_id") or next(
            (
                generics[g]
                for g in node.get("inherit_from", []) or []
                if generics.get(g)
            ),
            None,
        )
        if hfid:
            out[kind] = [str(h).split("__")[0] for h in hfid]
    return out


def check_identifiers_match_hfid(ctx: dict) -> tuple[bool, str]:
    """Each mapping's identifiers are the fields of the destination kind's human_friendly_id."""
    config = ctx["config"]
    if not isinstance(config, dict) or not isinstance(
        config.get("schema_mapping"), list
    ):
        return False, "identifiers-match-hfid: no schema_mapping list in config.yml"
    hfids = schema_hfids(ctx["schema"])
    problems = []
    for mapping in config["schema_mapping"]:
        if not isinstance(mapping, dict) or mapping.get("name") not in hfids:
            continue
        want = hfids[mapping["name"]]
        got = mapping.get("identifiers") or []
        if not isinstance(got, list) or set(map(str, got)) != set(want):
            problems.append(
                f"{mapping['name']}: identifiers {got} vs human_friendly_id fields {want}"
            )
    mapped = {m.get("name") for m in config["schema_mapping"] if isinstance(m, dict)}
    if set(hfids) - mapped:
        problems.append(f"no mapping for {sorted(set(hfids) - mapped)}")
    if problems:
        return False, "identifiers-match-hfid: " + "; ".join(problems)
    return True, "identifiers-match-hfid: identifiers match every human_friendly_id"


# --------------------------------------------------------------------------
# Task 6: changes stay in adapter files
# --------------------------------------------------------------------------

_ALLOWED = (
    re.compile(r"^infrahub_sync/adapters/servicenow\.py$"),
    re.compile(r"^tests/"),
    re.compile(r"^examples/"),
    re.compile(r"^docs/"),
    re.compile(r"^changelog/"),
    re.compile(r"^(dev/)?specs/"),
    re.compile(r"^[^/]+\.md$"),  # issue drafts or notes at the top level
    re.compile(r"^\.vale/styles/spelling-exceptions\.txt$"),
)
# Left by running the tests or the linters; not part of the change.
_CACHE_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def check_diff_stays_in_adapter(ctx: dict) -> tuple[bool, str]:
    """Every changed file is the adapter module or a test, example, doc, changelog or spec file."""
    root = ctx["output_dir"]
    files = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not _CACHE_PARTS & set(p.relative_to(root).parts)
    ]
    if not any(f == "infrahub_sync/adapters/servicenow.py" for f in files):
        return (
            False,
            "diff-stays-in-adapter: infrahub_sync/adapters/servicenow.py was not changed",
        )
    outside = [f for f in files if not any(rx.match(f) for rx in _ALLOWED)]
    if outside:
        return (
            False,
            f"diff-stays-in-adapter: files outside the adapter changed: {outside}",
        )
    return (
        True,
        "diff-stays-in-adapter: only adapter, test, example, doc and changelog files changed",
    )


# --------------------------------------------------------------------------
# Registry and runner
# --------------------------------------------------------------------------

CHECKS: dict[str, Callable[[dict], tuple[bool, str]]] = {
    "behavior-keys": check_behavior_keys,
    "behavior-covers-endpoints": check_behavior_covers_endpoints,
    "behavior-next-link": check_behavior_next_link,
    "behavior-rate-limit": check_behavior_rate_limit,
    "behavior-field-quirks": check_behavior_field_quirks,
    "fake-serves-captures": check_fake_serves_captures,
    "fake-field-selection": check_fake_field_selection,
    "fake-drops-unknown": check_fake_drops_unknown,
    "fake-reference-shapes": check_fake_reference_shapes,
    "fake-next-link": check_fake_next_link,
    "pr-checks-complete": check_pr_checks_complete,
    "retry-status-set": check_retry_status_set,
    "retry-after-honored": check_retry_after_honored,
    "retry-after-cap": check_retry_after_cap,
    "backoff-capped-jitter": check_backoff_capped_jitter,
    "no-tls-retry": check_no_tls_retry,
    "identifiers-match-hfid": check_identifiers_match_hfid,
    "diff-stays-in-adapter": check_diff_stays_in_adapter,
}


def build_context(workdir: Path) -> dict:
    """Load every artifact a task might produce; checks read what they need."""
    behavior, _ = load_yaml_file(workdir / "api-behavior.yml")
    py, py_err = load_python(workdir / "servicenow_client.py")
    if py is not None:
        py = _strip_docstrings(py)
    config, _ = load_yaml_file(workdir / "config.yml")
    pr = workdir / "PR_DESCRIPTION.md"
    schema = yaml.safe_load((DATA.parent / "task5_schema.yml").read_text())
    return {
        "workdir": workdir,
        "output_dir": workdir / "output",
        "behavior": behavior,
        "py": py,
        "py_err": py_err,
        "config": config,
        "schema": schema,
        "pr_text": pr.read_text() if pr.exists() else None,
    }


def run_checks(check_names: list[str], workdir: Path = Path()) -> dict:
    ctx = build_context(workdir)
    entries, passed = [], 0
    for name in check_names:
        try:
            ok, msg = CHECKS[name](ctx)
        except Exception as exc:  # noqa: BLE001 - a crashing check fails, it does not abort the run
            ok, msg = False, f"{name}: Error running check: {exc!r}"
        passed += ok
        entries.append({"name": name, "passed": ok, "message": msg})
    total = len(check_names)
    failed = [e["name"] for e in entries if not e["passed"]]
    return {
        "score": round(passed / total, 4) if total else 0.0,
        "details": f"{passed}/{total} checks passed."
        + (f" Failed: {', '.join(failed)}" if failed else ""),
        "checks": entries,
    }
