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
import os
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
                "methods": set(),
                "next_params": set(),
                "rate_limited": False,
                "reference_set": False,
                "reference_empty": False,
                "dropped_fields": set(),
                "object_fields": set(),
                "empty_fields": set(),
            },
        )
        entry["methods"].add(cap["request"].get("method", "GET"))
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
            for key, value in row.items():
                if isinstance(value, dict) and {"link", "value"} <= value.keys():
                    entry["reference_set"] = True
                    entry["object_fields"].add(key)
                elif value == "":
                    entry["empty_fields"].add(key)
    # An empty reference is "" for a field that is an object in another row,
    # possibly in another capture of the same endpoint.
    for entry in facts.values():
        entry["reference_empty"] = bool(entry["object_fields"] & entry["empty_fields"])
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
    """The entry whose path is exactly this endpoint (a query string is ignored)."""
    for entry in entries:
        if isinstance(entry.get("path"), str) and endpoint_path(entry["path"]) == path:
            return entry
    return None


def check_behavior_keys(ctx: dict) -> tuple[bool, str]:
    """Every endpoint entry is a mapping with the fixed key set and the captured method."""
    doc = ctx["behavior"]
    entries = _behavior_entries(doc)
    if not entries:
        return False, "behavior-keys: no `endpoints` list in api-behavior.yml"
    problems = []
    scalars = [e for e in doc["endpoints"] if not isinstance(e, dict)]
    if scalars:
        problems.append(f"entries that are not mappings: {scalars}")
    gaps = {
        e.get("path", "?"): [k for k in BEHAVIOR_KEYS if k not in e] for e in entries
    }
    gaps = {p: ks for p, ks in gaps.items() if ks}
    if gaps:
        problems.append(f"entries missing keys: {gaps}")
    for path, facts in captured_endpoints().items():
        entry = _entry_for(entries, path)
        if (
            entry is not None
            and str(entry.get("method", "")).upper() not in facts["methods"]
        ):
            problems.append(
                f"{path}: method {entry.get('method')!r}, captured {sorted(facts['methods'])}"
            )
    if problems:
        return False, "behavior-keys: " + "; ".join(problems)
    return (
        True,
        "behavior-keys: every entry has the fixed key set and the captured method",
    )


def check_behavior_covers_endpoints(ctx: dict) -> tuple[bool, str]:
    """One entry per captured endpoint, and no entry for an endpoint never captured."""
    entries = _behavior_entries(ctx["behavior"])
    captured = set(captured_endpoints())
    paths = [
        endpoint_path(e["path"]) for e in entries if isinstance(e.get("path"), str)
    ]
    problems = []
    missing = sorted(captured - set(paths))
    if missing:
        problems.append(f"no entry for captured endpoints {missing}")
    duplicates = sorted({p for p in paths if paths.count(p) > 1})
    if duplicates:
        problems.append(f"more than one entry for {duplicates}")
    extra = sorted(set(paths) - captured)
    if extra:
        problems.append(f"entries for endpoints never captured {extra}")
    if problems:
        return False, "behavior-covers-endpoints: " + "; ".join(problems)
    return True, "behavior-covers-endpoints: one entry per captured endpoint"


def check_behavior_next_link(ctx: dict) -> tuple[bool, str]:
    """A captured next link means `pagination.type: link_header`, and
    `next_link_carries` lists exactly the parameters that link repeats."""
    entries = _behavior_entries(ctx["behavior"])
    problems = []
    for path, facts in captured_endpoints().items():
        if not facts["next_params"]:
            continue
        entry = _entry_for(entries, path) or {}
        pag = (
            entry.get("pagination") if isinstance(entry.get("pagination"), dict) else {}
        )
        if pag.get("type") != "link_header":
            problems.append(
                f"{path} type is {pag.get('type')!r}, the capture has a Link header"
            )
        carries = pag.get("next_link_carries") or []
        carries = {str(c) for c in carries} if isinstance(carries, list) else set()
        # The parameter that moves the page is left out of the comparison: listing it is harmless.
        carries -= {"sysparm_offset", str(pag.get("cursor_param"))}
        if carries != facts["next_params"]:
            problems.append(
                f"{path} carries {sorted(carries)}, the captured link repeats {sorted(facts['next_params'])}"
            )
    if problems:
        return (
            False,
            "behavior-next-link: pagination does not match the captured next link: "
            + "; ".join(problems),
        )
    return True, "behavior-next-link: pagination matches the captured next links"


def check_behavior_rate_limit(ctx: dict) -> tuple[bool, str]:
    """A captured 429 is recorded with status 429 and a Retry-After header; an
    endpoint with no captured 429 does not claim one."""
    entries = _behavior_entries(ctx["behavior"])
    problems = []
    for path, facts in captured_endpoints().items():
        rl = (_entry_for(entries, path) or {}).get("rate_limit")
        if facts["rate_limited"]:
            if (
                not isinstance(rl, dict)
                or rl.get("status") != 429
                or rl.get("retry_after_header") is not True
            ):
                problems.append(
                    f"{path}: the captured 429 with Retry-After is not recorded"
                )
        elif isinstance(rl, dict) and (
            rl.get("status") == 429 or rl.get("observed") is True
        ):
            problems.append(
                f"{path}: records a 429 no capture shows (use observed: false)"
            )
    if problems:
        return False, "behavior-rate-limit: " + "; ".join(problems)
    return True, "behavior-rate-limit: rate limits recorded as captured"


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


def run_probe(script: str, workdir: Path, *args: str) -> dict:
    """Run one probe script against answer code in ``workdir``; return its JSON report.

    The probe imports model-written code, so it runs in a child process with an
    empty environment (no API key or token in reach), from inside ``workdir``,
    and confines itself with ``_sandbox.confine`` before the import.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(_HERE / script), str(workdir.resolve()), *args],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir.resolve()),
            env={"PATH": os.defpath, "HOME": str(workdir.resolve()), "LANG": "C.UTF-8"},
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": "probe timed out after 60 s"}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"error": f"probe crashed: {proc.stderr.strip()[-400:]}"}


def run_fake_probe(output_dir: Path) -> dict:
    """Run ``_fake_probe.py`` against the model's fake; return its JSON report."""
    if not output_dir.is_dir():
        return {"error": f"no {output_dir}/ directory: the fake was not written there"}
    return run_probe("_fake_probe.py", output_dir, str(DATA))


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


def _captured_page() -> list[dict]:
    """The rows of the captured cmdb_ci_netgear page, in order, as the probe's requests target it."""
    cap = json.loads((DATA / "cmdb_ci_netgear_page1.json").read_text())
    return [r for r in cap["body"]["result"] if isinstance(r, dict)]


# The "selected" scenario of _fake_probe.py asks cmdb_ci_netgear for these fields.
_SELECTED_FIELDS = ("sys_id", "name")


def check_fake_serves_captures(ctx: dict) -> tuple[bool, str]:
    """The fake returns the captured page: every row, in order, with the captured values."""
    sc, err = _scenario(ctx, "selected")
    if sc is None:
        return False, f"fake-serves-captures: {err}"
    expected = [
        {k: v for k, v in row.items() if k in _SELECTED_FIELDS}
        for row in _captured_page()
    ]
    if sc["rows"] != expected:
        return (
            False,
            f"fake-serves-captures: asked for sys_id,name and got {sc['rows'][:3]}, "
            f"the capture gives {expected}",
        )
    return (
        True,
        "fake-serves-captures: the captured rows, in order, with the captured values",
    )


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
    """The captured request gets the captured rows back unchanged, references included:
    {link, value} when set and "" when empty."""
    sc, err = _scenario(ctx, "references")
    if sc is None:
        return False, f"fake-reference-shapes: {err}"
    expected = _captured_page()
    if sc["rows"] != expected:
        got = [r.get("location") for r in sc["rows"]]
        want = [r.get("location") for r in expected]
        return (
            False,
            f"fake-reference-shapes: the captured request returns rows that differ from the capture "
            f"(location values {got[:4]}, captured {want})",
        )
    return (
        True,
        "fake-reference-shapes: object when set, empty string when empty, as captured",
    )


def check_fake_next_link(ctx: dict) -> tuple[bool, str]:
    """The captured page's next link is served exactly as captured, and following
    it does not serve the first page again."""
    sc, err = _scenario(ctx, "captured_page")
    if sc is None:
        return False, f"fake-next-link: {err}"
    if sc.get("next") != sc.get("expected_next"):
        return (
            False,
            f"fake-next-link: next link {sc.get('next')!r} differs from the captured {sc.get('expected_next')!r}",
        )
    nxt = _probe(ctx).get("next_page") or {}
    first_ids = [r.get("sys_id") for r in _captured_page()]
    if (
        nxt.get("status") == 200
        and [r.get("sys_id") for r in nxt.get("rows", [])] == first_ids
    ):
        return (
            False,
            "fake-next-link: following the next link serves the first page again; "
            "the fake ignores the query string of the link",
        )
    return (
        True,
        "fake-next-link: next link served as captured, and not answered with page 1",
    )


# --------------------------------------------------------------------------
# Task 3: PR check list
# --------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_SECTION_WORDS = re.compile(r"check|test|verif|validat|gate", re.IGNORECASE)


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


_INLINE = re.compile(r"`([^`\n]+)`")
_FENCE_BLOCK = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
_PRINTERS = {"echo", "printf"}


def _entries(section: str) -> list[str]:
    """List items (with their indented continuation lines) and table rows, fences removed."""
    entries: list[str] = []
    for line in _FENCE_BLOCK.sub("", section).splitlines():
        if not line.strip():
            continue
        if (
            line.startswith((" ", "\t"))
            and entries
            and not line.lstrip().startswith(("-", "*", "|"))
        ):
            entries[-1] += " " + line.strip()
        else:
            entries.append(line.strip())
    return entries


def _tokens(span: str) -> list[str]:
    span = span.strip().lstrip("$ ").strip()
    try:
        tokens = shlex.split(span)
    except ValueError:
        tokens = span.split()
    return [] if tokens and tokens[0] in _PRINTERS else tokens


def _pr_entries(section: str) -> list[tuple[list[list[str]], bool]]:
    """For each entry: the token lists of its code spans, and whether text after the
    first code span reports a result."""
    out = []
    for entry in _entries(section):
        spans = _INLINE.findall(entry)
        if not spans:
            continue
        after = entry.split("`" + spans[0] + "`", 1)[1]
        result = re.search(r"[A-Za-z0-9]", _INLINE.sub("", after)) is not None
        out.append(([_tokens(span) for span in spans], result))
    return out


def _has_seq(tokens: list[str], seq: list[str]) -> bool:
    return any(tokens[i : i + len(seq)] == seq for i in range(len(tokens)))


def _names_adapter(tokens: list[str]) -> bool:
    return any("servicenow" in t.lower() for t in tokens)


# Commands need a result written after them; a changed path is its own evidence.
PR_COMMANDS: dict[str, Callable[[list[str]], bool]] = {
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
    "infrahub-sync generate": lambda t: (
        _has_seq(t, ["infrahub-sync", "generate"]) and _names_adapter(t)
    ),
    "infrahub-sync diff": lambda t: (
        _has_seq(t, ["infrahub-sync", "diff"]) and _names_adapter(t)
    ),
}
PR_PATHS: dict[str, Callable[[list[str]], bool]] = {
    "news fragment": lambda t: (
        "towncrier" in t or any(re.match(r"^changelog/.+\.md$", x) for x in t)
    ),
    "docs page": lambda t: "docs/docs/adapters/servicenow.mdx" in t,
    "docs sidebar": lambda t: any(x.endswith("sidebars.ts") for x in t),
    "choosing-an-adapter row": lambda t: any(
        x.endswith("choosing-an-adapter.mdx") for x in t
    ),
    "spec documents": lambda t: any("specs/" in x and "servicenow" in x for x in t),
}
PR_ITEMS = {**PR_COMMANDS, **PR_PATHS}


def check_pr_checks_complete(ctx: dict) -> tuple[bool, str]:
    """The PR's checks section names every required check: each command with its
    result, each changed path, all for the ServiceNow adapter."""
    text = ctx["pr_text"]
    if text is None:
        return False, "pr-checks-complete: PR_DESCRIPTION.md not found"
    section = _checks_section(text)
    if section is None:
        return (
            False,
            "pr-checks-complete: no checks section (a heading naming checks, tests, verification or validation)",
        )
    entries = _pr_entries(section)
    missing, no_result = [], []
    for name, hit in PR_ITEMS.items():
        found = [result for spans, result in entries for t in spans if hit(t)]
        if not found:
            missing.append(name)
        elif name in PR_COMMANDS and not any(found):
            no_result.append(name)
    problems = []
    if missing:
        problems.append(f"the checks section omits {missing}")
    if no_result:
        problems.append(f"no result written after {no_result}")
    if problems:
        return False, "pr-checks-complete: " + "; ".join(problems)
    return True, "pr-checks-complete: every required check is listed with its result"


# --------------------------------------------------------------------------
# Task 4: retry policy (run against scripted responses, plus the AST for the cap)
# --------------------------------------------------------------------------

RETRY_STATUSES = {429, 502, 503, 504}
NOT_RETRIED = {"ok": 200, "s500": 500, "s404": 404}


def _retry_report(ctx: dict) -> dict:
    if "retry_probe" not in ctx:
        path = ctx["workdir"] / "servicenow_client.py"
        ctx["retry_probe"] = (
            run_probe("_retry_probe.py", ctx["workdir"])
            if path.exists()
            else {"error": "servicenow_client.py not found"}
        )
    return ctx["retry_probe"]


def _scenarios(ctx: dict, check: str) -> tuple[dict | None, str]:
    report = _retry_report(ctx)
    if report.get("error"):
        return None, f"{check}: {report['error']}"
    return report, ""


def _retried_once_then_ok(entry: dict) -> bool:
    return entry.get("calls") == 2 and entry.get("status") == 200


def check_retry_status_set(ctx: dict) -> tuple[bool, str]:
    """429, 502, 503 and 504 are retried; 200, 404 and 500 are not."""
    report, err = _scenarios(ctx, "retry-status-set")
    if report is None:
        return False, err
    wrong = [
        f"HTTP {status} not retried ({report[f's{status}']})"
        for status in sorted(RETRY_STATUSES)
        if not _retried_once_then_ok(report[f"s{status}"])
    ] + [
        f"HTTP {status} retried ({report[name]})"
        for name, status in NOT_RETRIED.items()
        if report[name].get("calls") != 1
    ]
    if wrong:
        return False, "retry-status-set: " + "; ".join(wrong)
    return True, "retry-status-set: retries 429, 502, 503 and 504 only"


def check_retry_after_honored(ctx: dict) -> tuple[bool, str]:
    """The client waits exactly the Retry-After seconds, up to 300 s included."""
    report, err = _scenarios(ctx, "retry-after-honored")
    if report is None:
        return False, err
    wrong = []
    for name, seconds in (("retry_after_30", 30.0), ("retry_after_300", 300.0)):
        entry = report[name]
        if entry.get("status") != 200 or entry.get("waits", [None])[:1] != [seconds]:
            wrong.append(f"Retry-After {seconds:.0f}: {entry}")
    if wrong:
        return (
            False,
            "retry-after-honored: the wait is not the Retry-After value: "
            + "; ".join(wrong),
        )
    return True, "retry-after-honored: the client waits the Retry-After seconds"


def check_retry_after_cap(ctx: dict) -> tuple[bool, str]:
    """A Retry-After above 300 s raises at once, without waiting."""
    report, err = _scenarios(ctx, "retry-after-cap")
    if report is None:
        return False, err
    wrong = [
        f"Retry-After {name.rsplit('_', 1)[1]}: {report[name]}"
        for name in ("retry_after_301", "retry_after_1422")
        if report[name].get("ended") != "raised"
        or report[name].get("calls") != 1
        or report[name].get("waits")
    ]
    if wrong:
        return (
            False,
            "retry-after-cap: a wait over 300 s does not stop the run: "
            + "; ".join(wrong),
        )
    return True, "retry-after-cap: a Retry-After over 300 s raises without waiting"


def check_no_tls_retry(ctx: dict) -> tuple[bool, str]:
    """Dropped and timed-out connections are retried; a TLS error is raised at once."""
    report, err = _scenarios(ctx, "no-tls-retry")
    if report is None:
        return False, err
    wrong = [
        f"{name} not retried ({report[name]})"
        for name in ("connection_error", "timeout")
        if not _retried_once_then_ok(report[name])
    ]
    ssl = report["ssl_error"]
    if ssl.get("ended") != "raised" or ssl.get("calls") != 1:
        wrong.append(f"SSLError retried ({ssl})")
    if wrong:
        return False, "no-tls-retry: " + "; ".join(wrong)
    return True, "no-tls-retry: connection errors retried, TLS errors raised"


def check_shared_retry_budget(ctx: dict) -> tuple[bool, str]:
    """Retries end, and status and connection retries draw on one budget."""
    report, err = _scenarios(ctx, "shared-retry-budget")
    if report is None:
        return False, err
    runs = {n: report[n] for n in ("always_503", "always_connection_error", "mixed")}
    unbounded = [n for n, e in runs.items() if e.get("ended") == "unbounded"]
    if unbounded:
        return False, f"shared-retry-budget: retries never stop for {unbounded}"
    single = max(runs["always_503"]["calls"], runs["always_connection_error"]["calls"])
    if runs["mixed"]["calls"] > single:
        return (
            False,
            f"shared-retry-budget: alternating failures made {runs['mixed']['calls']} requests, "
            f"more than the {single} one kind allows: two separate budgets",
        )
    return True, "shared-retry-budget: one budget for status and connection retries"


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


# The 60 s cap is read from the code: with a budget of five retries, 2**5 = 32 s
# never reaches it, so the scripted run cannot show it. Each expression carries
# labels: jitter (derived from a random draw) and capped (bounded at 60 s by
# min(..., 60) or by `if x > 60: x = 60`). Labels pass through assignments,
# through a call that takes a labelled argument, and through functions whose
# return value is labelled. Adding or subtracting keeps `capped` only when both
# sides are capped, so min(60, x) + uniform(0, 5) is not capped. The analysis
# ignores statement order inside a function.

_RANDOM_MODULES = ("random", "secrets")


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
        if isinstance(expr, ast.Name):
            return set(self.var.get((scope, expr.id), set()))
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Sub)):
            left, right = self.labels(expr.left, scope), self.labels(expr.right, scope)
            out = (left | right) - {"capped"}
            if "capped" in left and "capped" in right:
                out.add("capped")
            return out
        if isinstance(expr, ast.IfExp):
            body, orelse = (
                self.labels(expr.body, scope),
                self.labels(expr.orelse, scope),
            )
            out = (body | orelse) - {"capped"}
            if "capped" in body and "capped" in orelse:
                out.add("capped")
            return out
        out: set[str] = set()
        if isinstance(expr, ast.Call):
            name = _call_name(expr.func)
            if (
                isinstance(expr.func, ast.Attribute)
                and isinstance(expr.func.value, ast.Name)
                and expr.func.value.id in _RANDOM_MODULES
            ) or (
                isinstance(expr.func, ast.Name) and expr.func.id in self.random_names
            ):
                out.add("jitter")
            if name == "min" and any(_num(a, self.names) == 60 for a in expr.args):
                out.add("capped")
            if name:
                out |= self.ret.get(name, set())
        for child in ast.iter_child_nodes(expr):
            if isinstance(child, ast.expr):
                out |= self.labels(child, scope)
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


def check_backoff_capped_jitter(ctx: dict) -> tuple[bool, str]:
    """Backoff waits (repeated dropped connections) vary between runs and stay at or
    below 60 s, and the slept backoff is capped at 60 s in the code."""
    report, err = _scenarios(ctx, "backoff-capped-jitter")
    if report is None:
        return False, err
    first = report["always_connection_error"]["waits"]
    second = report["always_connection_error_seed2"]["waits"]
    problems = []
    if len(first) < 2:
        problems.append(
            f"fewer than two backoff waits on repeated connection errors ({first})"
        )
    if any(w > 60 for w in first + second):
        problems.append(f"a wait above 60 s ({max(first + second)})")
    if first == second:
        problems.append(f"the same waits with two random seeds, so no jitter ({first})")
    tree = ctx["py"]
    if tree is None or not any(
        {"capped", "jitter"} <= lbl for lbl in _Flow(tree).sleeps()
    ):
        problems.append("no sleep() waits on a value both capped at 60 s and jittered")
    if problems:
        return False, "backoff-capped-jitter: " + "; ".join(problems)
    return True, "backoff-capped-jitter: jittered backoff capped at 60 s"


# --------------------------------------------------------------------------
# Task 6: changes stay in adapter files
# --------------------------------------------------------------------------

# The adapter's own files, as rules/scope-adapter-files-only.md lists them for <name>=servicenow.
_ALLOWED = (
    re.compile(r"^infrahub_sync/adapters/servicenow\.py$"),
    # its tests, fixtures and fakes, wherever the test layout puts them
    re.compile(r"^tests/(.+/)?[^/]*servicenow[^/]*(/.+)?$"),
    re.compile(r"^examples/servicenow[^/]*/.+"),
    re.compile(r"^docs/docs/adapters/(servicenow|choosing-an-adapter)\.mdx$"),
    re.compile(r"^docs/docs/readme\.mdx$"),
    re.compile(r"^docs/sidebars\.ts$"),
    re.compile(r"^changelog/[^/]+\.md$"),
    re.compile(r"^(dev/)?specs/[^/]*servicenow[^/]*/.+"),
    # README.md and AGENTS.md (the adapter lists), and drafted issues or notes
    re.compile(r"^[^/]+\.md$"),
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
    "shared-retry-budget": check_shared_retry_budget,
    "diff-stays-in-adapter": check_diff_stays_in_adapter,
}


def build_context(workdir: Path) -> dict:
    """Load every artifact a task might produce; checks read what they need."""
    behavior, _ = load_yaml_file(workdir / "api-behavior.yml")
    py, py_err = load_python(workdir / "servicenow_client.py")
    if py is not None:
        py = _strip_docstrings(py)
    pr = workdir / "PR_DESCRIPTION.md"
    return {
        "workdir": workdir,
        "output_dir": workdir / "output",
        "behavior": behavior,
        "py": py,
        "py_err": py_err,
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
