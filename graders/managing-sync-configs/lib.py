"""Grader library for the infrahub-managing-sync-configs skill.

Every check parses its artifact: the sync config through ``yaml.safe_load``,
and the destination schema from ``data/netbox_schema.yml``, the same schema
the eval prompt shows, so the graders hold no second copy of it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
DATA = _HERE / "data"

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


# --------------------------------------------------------------------------
# Identifiers match the human-friendly ID
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


def _mapped_fields(mapping: dict) -> set[str]:
    """Field names of one schema_mapping entry that take their value from the source."""
    return {
        str(f.get("name"))
        for f in mapping.get("fields") or []
        if isinstance(f, dict)
        and f.get("name")
        and (f.get("mapping") or f.get("static") is not None)
    }


def check_identifiers_match_hfid(ctx: dict) -> tuple[bool, str]:
    """Each mapping's identifiers are the fields of the destination kind's human_friendly_id,
    listed once each and mapped from the source in the same entry."""
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
        name = mapping["name"]
        want = hfids[name]
        got = mapping.get("identifiers") or []
        if not isinstance(got, list):
            problems.append(f"{name}: identifiers is not a list")
            continue
        got = [str(g) for g in got]
        if set(got) != set(want) or len(got) != len(set(got)):
            problems.append(
                f"{name}: identifiers {got} vs human_friendly_id fields {want}"
            )
        unmapped = sorted(set(got) - _mapped_fields(mapping))
        if unmapped:
            problems.append(f"{name}: identifiers {unmapped} have no field mapping")
    mapped = {m.get("name") for m in config["schema_mapping"] if isinstance(m, dict)}
    if set(hfids) - mapped:
        problems.append(f"no mapping for {sorted(set(hfids) - mapped)}")
    if problems:
        return False, "identifiers-match-hfid: " + "; ".join(problems)
    return True, "identifiers-match-hfid: identifiers match every human_friendly_id"


# The stable source ID the prompt asks to keep, per destination kind.
_STABLE_ID = {"NetworkDevice": "netbox_id", "LocationSite": "netbox_id"}


def check_stable_id_is_a_field(ctx: dict) -> tuple[bool, str]:
    """The source's stable ID is mapped as an ordinary field, not used as a key."""
    config = ctx["config"]
    if not isinstance(config, dict) or not isinstance(
        config.get("schema_mapping"), list
    ):
        return False, "stable-id-is-a-field: no schema_mapping list in config.yml"
    problems = []
    entries = {
        m.get("name"): m for m in config["schema_mapping"] if isinstance(m, dict)
    }
    for kind, field in _STABLE_ID.items():
        mapping = entries.get(kind)
        if mapping is None:
            problems.append(f"no mapping for {kind}")
            continue
        if field not in _mapped_fields(mapping):
            problems.append(f"{kind}: {field} is not mapped as a field")
        if field in [str(i) for i in mapping.get("identifiers") or []]:
            problems.append(f"{kind}: {field} is used as an identifier")
    if problems:
        return False, "stable-id-is-a-field: " + "; ".join(problems)
    return True, "stable-id-is-a-field: the NetBox id is kept as an ordinary field"


# --------------------------------------------------------------------------
# Registry and runner
# --------------------------------------------------------------------------

CHECKS: dict[str, Callable[[dict], tuple[bool, str]]] = {
    "identifiers-match-hfid": check_identifiers_match_hfid,
    "stable-id-is-a-field": check_stable_id_is_a_field,
}


def build_context(workdir: Path) -> dict:
    """Load every artifact a task might produce; checks read what they need."""
    config, _ = load_yaml_file(workdir / "config.yml")
    schema = yaml.safe_load((DATA / "netbox_schema.yml").read_text())
    return {"workdir": workdir, "config": config, "schema": schema}


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
