"""Shared grader library for infrahub-planning-upgrades skill evaluations.

The model is prompted to write a version-by-version upgrade plan to
``UPGRADE_PLAN.md`` in the cwd. The document has one ``##`` section per
version hop, in ascending order, each carrying a findings table with these
nine columns:

    | Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |

Every check here parses that structure — hop headings, table rows split into
named cells, fenced command blocks tokenised with ``shlex`` — and none of
them substring-matches the prose. See ``dev/guidelines/graders.md``.

Each check returns ``(bool, str)``: pass/fail plus a one-line message that
lands in the skillgrade report.

Known limit, recorded deliberately: ``check_one_upgrade_per_hop`` asserts the
*structure* of the plan (each hop carries its own upgrade step) rather than
trying to detect prose that recommends combining hops. Phrase-matching that
recommendation was rejected — it grades vocabulary. A plan that lays out
correct per-hop commands and then adds a stray sentence suggesting they be
combined is not caught here; that is a trade accepted in favour of a check
that cannot be laundered by wording.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

PLAN_FILE = "UPGRADE_PLAN.md"

REQUIRED_COLUMNS = [
    "change",
    "release",
    "kind",
    "severity",
    "when",
    "affected",
    "evidence",
    "action",
    "source",
]

VALID_KIND = {"breaking", "preparation"}
VALID_SEVERITY = {"critical", "warning", "info"}
VALID_WHEN = {"before", "during", "after"}
VALID_AFFECTED = {"yes", "no", "unknown"}

# Read-only probes the plan may show, as token prefixes. An allowlist rather
# than a blocklist on purpose: `infrahubctl schema load` puts its verb in the
# *third* token, so anything keyed on the first subcommand lets a write past.
READ_ONLY_INVOCATIONS = [
    ("infrahubctl", "info"),
    ("infrahubctl", "version"),
    ("infrahubctl", "schema", "check"),
    ("infrahubctl", "branch", "list"),
    ("infrahub", "db", "showmigrations"),
    ("infrahub", "upgrade"),  # further narrowed below: only with --check
]

# `infrahubctl` has no `upgrade` command at all — it lives server-side in
# backend/infrahub/cli/upgrade.py. Writing it is an invented command, which is
# the exact failure mode safety-read-only-probes exists to catch. It is listed
# separately so the message says "invented", not "not allowed".
NONEXISTENT_INVOCATIONS = [("infrahubctl", "upgrade")]

_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b")
_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.S | re.M)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")

# Evidence that names something locatable, strongest first.
_EV_PATH = re.compile(r"[\w./-]+\.(?:ya?ml|py|gql|graphql|j2|toml|json|cfg)\b")
_EV_DOTTED_KIND = re.compile(r"\b[A-Z][A-Za-z0-9]+\.[a-z_][A-Za-z0-9_]*\b")
_EV_KIND = re.compile(
    r"\b(?:Core|Infra|Builtin|Dcim|Location|Organization|Ipam|Template|Nested|Profile)"
    r"[A-Z][A-Za-z0-9]+\b"
)
_EV_COUNT = re.compile(
    r"\b\d+\s+(?:node|object|instance|device|match|result|row|occurrence|hit)s?\b", re.I
)
_EV_PROBE = re.compile(
    r"\b(?:get_schema|query_graphql|get_nodes|search_nodes|showmigrations|infrahubctl|infrahub)\b"
)

_NO_EVIDENCE_SENTINELS = {"", "-", "--", "n/a", "na", "none", "tbd", "?"}


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------


def _versions(text: str) -> list[tuple[int, int]]:
    """Every version in the text as (major, minor); patch is deliberately dropped."""
    return [(int(m.group(1)), int(m.group(2))) for m in _VERSION_RE.finditer(text)]


def _full_versions(text: str) -> list[str]:
    """Every version in the text, as written."""
    return [m.group(0) for m in _VERSION_RE.finditer(text)]


def hop_sections(text: str) -> list[dict]:
    """Split the plan into ``##`` sections that name two or more versions.

    A hop heading is any level-2 heading carrying at least two versions, so
    ``## 1.6 -> 1.7`` and ``## Step 1 - 1.6.3 to 1.7.7`` both parse. Headings
    with fewer than two versions (``## Summary``) are not hops.
    """
    sections: list[dict] = []
    current: dict | None = None
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if current is not None:
                current["lines"].append(line)
            continue
        if in_fence:
            # A `# comment` inside a fenced block is not a heading.
            if current is not None:
                current["lines"].append(line)
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            vs = _versions(heading)
            if len(vs) >= 2:
                current = {"heading": heading, "from": vs[0], "to": vs[-1], "lines": []}
                sections.append(current)
            else:
                current = None
            continue
        if line.startswith("# "):
            current = None
            continue
        if current is not None:
            current["lines"].append(line)
    for s in sections:
        s["body"] = "\n".join(s["lines"])
    return sections


def tables(body: str) -> list[list[dict]]:
    """Parse every markdown table in ``body`` into a list of row dicts."""
    out: list[list[dict]] = []
    rows = [ln.strip() for ln in body.splitlines()]
    block: list[str] = []
    for line in rows + [""]:
        if line.startswith("|"):
            block.append(line)
            continue
        if len(block) >= 2:
            parsed = _parse_table(block)
            if parsed:
                out.append(parsed)
        block = []
    return out


def _parse_table(block: list[str]) -> list[dict]:
    header = [c.strip().lower() for c in block[0].strip().strip("|").split("|")]
    body_rows = block[1:]
    # Drop the --- separator row if present.
    if body_rows and set(body_rows[0].replace("|", "").replace(":", "").strip()) <= {
        "-",
        " ",
    }:
        body_rows = body_rows[1:]
    parsed: list[dict] = []
    for row in body_rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if not any(cells):
            continue
        parsed.append(
            {header[i]: cells[i] for i in range(min(len(header), len(cells)))}
        )
    return parsed


def findings(text: str) -> list[dict]:
    """Every findings row across every hop, each tagged with its hop heading."""
    out: list[dict] = []
    for sec in hop_sections(text):
        for table in tables(sec["body"]):
            for row in table:
                if "change" in row and "affected" in row:
                    row = dict(row)
                    row["_hop"] = sec["heading"]
                    out.append(row)
    return out


def command_lines(text: str) -> list[str]:
    """Every command line from every fenced block, plus inline code spans.

    Extracts *all* fences, not the first, and drops comment and output lines
    so a ``#`` annotation cannot be read as a command.
    """
    lines: list[str] = []
    for block in _FENCE_RE.findall(text):
        for raw in block.splitlines():
            stripped = raw.strip().lstrip("$").strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
    for span in _INLINE_CODE_RE.findall(text):
        stripped = span.strip().lstrip("$").strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines


def invocations(text: str) -> list[tuple[str, tuple[str, ...], list[str]]]:
    """Every ``infrahub`` / ``infrahubctl`` invocation, as (binary, path, flags).

    ``path`` is the binary followed by its non-flag tokens, so
    ``infrahubctl schema load x.yml`` yields
    ``("infrahubctl", "schema", "load", "x.yml")``. Keying on the first
    subcommand alone would read that as ``schema`` and miss the write.

    Tokenised with ``shlex`` so quoting is honoured, then scanned for the
    target binary. This sees through wrappers — ``docker compose exec
    infrahub-server infrahub upgrade --check``, ``kubectl exec pod --
    infrahub db showmigrations``, ``uv run infrahubctl info`` — because it
    looks for the binary token rather than assuming it starts the line.
    """
    found: list[tuple[str, tuple[str, ...], list[str]]] = []
    for line in command_lines(text):
        for piece in re.split(r"&&|\|\||;|\|", line):
            try:
                tokens = shlex.split(piece.strip())
            except ValueError:
                continue
            for i, tok in enumerate(tokens):
                base = tok.rsplit("/", 1)[-1]
                if base in ("infrahub", "infrahubctl"):
                    rest = tokens[i + 1 :]
                    words = [t for t in rest if not t.startswith("-")]
                    flags = [t for t in rest if t.startswith("-")]
                    found.append((base, tuple([base, *words]), flags))
                    break
    return found


def _is_concrete_evidence(cell: str) -> bool:
    """Does the cell name something a reader could go and look at?

    Ranked, strongest first: a file path, a ``Kind.attribute`` reference, a
    schema kind, a counted result, or a named probe. Prose that merely
    restates the finding matches none of these.
    """
    value = cell.strip().strip("`").strip()
    if value.lower() in _NO_EVIDENCE_SENTINELS:
        return False
    for pattern in (_EV_PATH, _EV_DOTTED_KIND, _EV_KIND, _EV_COUNT, _EV_PROBE):
        if pattern.search(cell):
            return True
    return False


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def check_sequential_hops(
    text: str, source: str = "", target: str = ""
) -> tuple[bool, str]:
    """Hop headings enumerate every minor from source to target, ascending, no skips."""
    hops = hop_sections(text)
    if not hops:
        return (
            False,
            f"no hop sections found in {PLAN_FILE} (expected '## X.Y -> X.Z' headings)",
        )

    src = _versions(source)[0] if _versions(source) else hops[0]["from"]
    tgt = _versions(target)[0] if _versions(target) else hops[-1]["to"]

    expected = []
    cur = src
    guard = 0
    while cur != tgt and guard < 64:
        nxt = (cur[0], cur[1] + 1)
        expected.append((cur, nxt))
        cur = nxt
        guard += 1
    if not expected:
        return False, f"source {src} and target {tgt} describe no hop"

    def _fmt(pairs: list[tuple[tuple[int, int], tuple[int, int]]]) -> str:
        return ", ".join(f"{a[0]}.{a[1]}->{b[0]}.{b[1]}" for a, b in pairs)

    actual = [(h["from"], h["to"]) for h in hops]
    if len(actual) == 1 and len(expected) > 1:
        return False, (
            f"plan has a single hop {_fmt(actual)} but the N-1 rule "
            f"requires {len(expected)} sequential hops: {_fmt(expected)}"
        )
    if actual != expected:
        return False, f"hops are [{_fmt(actual)}], expected [{_fmt(expected)}]"
    return True, f"{len(actual)} sequential minor hops, no skips"


def check_one_upgrade_per_hop(text: str) -> tuple[bool, str]:
    """Every hop section carries its own upgrade step; hops are not consolidated."""
    hops = hop_sections(text)
    if not hops:
        return False, f"no hop sections found in {PLAN_FILE}"
    missing = [
        h["heading"]
        for h in hops
        if not any(
            path[:2] == ("infrahub", "upgrade") for _, path, _ in invocations(h["body"])
        )
    ]
    if missing:
        return False, (
            f"{len(missing)} of {len(hops)} hops carry no upgrade step of their own "
            f"(first: '{missing[0]}') — hops appear consolidated"
        )
    return True, f"each of {len(hops)} hops carries its own upgrade step"


def check_every_hop_enumerated(text: str, releases: str = "") -> tuple[bool, str]:
    """Findings name each intermediate release that carries a breaking change.

    Also rejects a ``Release`` cell holding a range rather than one version:
    ``1.6.0-1.9.0`` names no actual change and is the shape a plan reaches for
    when it wants credit for intermediate releases it never read.
    """
    rows = findings(text)
    if not rows:
        return False, f"no findings rows parsed from {PLAN_FILE}"

    ranged = [r for r in rows if len(_full_versions(r.get("release", ""))) > 1]
    if ranged:
        return False, (
            f"{len(ranged)} findings carry a version range in Release "
            f"(e.g. '{ranged[0].get('release')}') instead of a single release"
        )

    required = [v.strip() for v in releases.split(",") if v.strip()]
    if not required:
        return True, f"{len(rows)} findings, all stamped with a single release"

    seen = {r.get("release", "").strip() for r in rows}
    seen_mm = {tuple(_versions(s)[0]) for s in seen if _versions(s)}
    missing = []
    for req in required:
        req_mm = _versions(req)[0]
        if req not in seen and req_mm not in seen_mm:
            missing.append(req)
    if missing:
        return False, (
            f"no finding attributed to release(s) {', '.join(missing)}; "
            f"releases present: {', '.join(sorted(s for s in seen if s)) or '(none)'}"
        )
    return True, f"findings cover all {len(required)} required releases"


def check_verdict_has_evidence(text: str) -> tuple[bool, str]:
    """Every finding carries a verdict, and the verdict is backed by something locatable."""
    rows = findings(text)
    if not rows:
        return False, f"no findings rows parsed from {PLAN_FILE}"

    for row in rows:
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in row]
        if missing_cols:
            return False, (
                f"finding '{row.get('change', '?')}' is missing column(s): "
                f"{', '.join(missing_cols)}"
            )

    for row in rows:
        change = row.get("change", "?")
        affected = row.get("affected", "").strip().lower()
        if affected not in VALID_AFFECTED:
            return False, (
                f"finding '{change}' has Affected='{row.get('affected')}', "
                f"expected one of {sorted(VALID_AFFECTED)}"
            )
        if affected in ("yes", "no"):
            if not _is_concrete_evidence(row.get("evidence", "")):
                return False, (
                    f"finding '{change}' is Affected={affected} but Evidence "
                    f"'{row.get('evidence')}' names no locatable artifact "
                    f"(path, Kind.attribute, schema kind, count, or probe)"
                )
        else:
            if not _EV_PROBE.search(row.get("action", "")):
                return False, (
                    f"finding '{change}' is Affected=unknown but Action "
                    f"'{row.get('action')}' names no probe that would resolve it"
                )
    return True, f"all {len(rows)} findings carry a backed verdict"


def check_finding_vocabulary(text: str) -> tuple[bool, str]:
    """Kind, Severity and When use the documented enums."""
    rows = findings(text)
    if not rows:
        return False, f"no findings rows parsed from {PLAN_FILE}"
    for row in rows:
        for col, valid in (
            ("kind", VALID_KIND),
            ("severity", VALID_SEVERITY),
            ("when", VALID_WHEN),
        ):
            value = row.get(col, "").strip().lower()
            if value not in valid:
                return False, (
                    f"finding '{row.get('change', '?')}' has {col.title()}='{row.get(col)}', "
                    f"expected one of {sorted(valid)}"
                )
    return True, f"all {len(rows)} findings use the documented enums"


def check_no_mutating_commands(text: str) -> tuple[bool, str]:
    """The plan shows only read-only probes, and no invented commands."""
    invoked = invocations(text)
    if not invoked:
        return False, f"{PLAN_FILE} shows no infrahub/infrahubctl invocation at all"

    for _binary, path, flags in invoked:
        shown = " ".join(path)
        for bad in NONEXISTENT_INVOCATIONS:
            if path[: len(bad)] == bad:
                return False, (
                    f"'{shown}' is not a real command — upgrade lives server-side in "
                    f"backend/infrahub/cli/upgrade.py, not in infrahubctl"
                )
        allowed = next((a for a in READ_ONLY_INVOCATIONS if path[: len(a)] == a), None)
        if allowed is None:
            return False, (
                f"'{shown}' is not on the read-only probe allowlist "
                f"(permitted: infrahubctl info, infrahubctl schema check, "
                f"infrahub db showmigrations, infrahub upgrade --check)"
            )
        if allowed == ("infrahub", "upgrade") and "--check" not in flags:
            return False, f"'{shown}' without --check writes to the database"
    return True, f"all {len(invoked)} invocations are read-only probes"


CHECKS = {
    "sequential-hops": check_sequential_hops,
    "one-upgrade-per-hop": check_one_upgrade_per_hop,
    "every-hop-enumerated": check_every_hop_enumerated,
    "verdict-has-evidence": check_verdict_has_evidence,
    "finding-vocabulary": check_finding_vocabulary,
    "no-mutating-commands": check_no_mutating_commands,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the plan text; return skillgrade JSON."""
    text = output_path.read_text(errors="ignore") if output_path.exists() else ""
    entries: list[dict] = []
    passed_count = 0

    for spec in check_specs:
        name, kwargs = spec if isinstance(spec, tuple) else (spec, {})
        fn = CHECKS.get(name)
        if fn is None:
            entries.append(
                {"name": name, "passed": False, "message": f"Unknown check: {name}"}
            )
            continue
        try:
            ok, msg = fn(text, **kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        display = (
            name
            if not kwargs
            else f"{name}({','.join(f'{k}={v}' for k, v in kwargs.items())})"
        )
        entries.append({"name": display, "passed": ok, "message": msg})

    total = len(check_specs)
    score = round(passed_count / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}


def main_cli() -> None:
    import sys

    if len(sys.argv) < 3:
        print("usage: python lib.py <output-file> <check-name> ...", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(run_checks(list(sys.argv[2:]), Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main_cli()
