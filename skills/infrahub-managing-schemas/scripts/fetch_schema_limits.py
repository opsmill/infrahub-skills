#!/usr/bin/env python3
"""Fetch the live Infrahub schema string-length / pattern constraints,
or use them to validate schema YAML files.

Cross-platform: uses Python's stdlib `urllib` for the fetch — no
shell pipes, no curl, no quoting differences between bash / zsh /
cmd.exe / PowerShell.

Modes
-----
* ``python fetch_schema_limits.py`` — print the constraint subset as
  compact JSON on stdout. Default source is the public JSON Schema
  export at ``https://schema.infrahub.app/infrahub/schema/latest.json``.
* ``python fetch_schema_limits.py --openapi BASE_URL`` — read the same
  constraints from a running Infrahub instance's
  ``/api/openapi.json`` instead. Useful when the public source is
  unreachable and a server has been located via
  ``connectivity-server-check.md``.
* ``python fetch_schema_limits.py --check FILE [FILE ...]`` —
  validate the named schema YAML files against the live ``maxLength``
  caps. Prints one issue per over-cap field. Composes with
  ``--openapi``.

The JSON output is keyed by schema name (``NodeSchema``,
``GenericSchema``, ``AttributeSchema``, ``RelationshipSchema``).
Schemas without ``-Input`` / ``-Output`` variants in the OpenAPI
spec are normalised to the JSON Schema names so the output structure
is identical regardless of source.

Exit codes
----------
Without ``--check``:
  0  Constraints printed to stdout.
  1  Source unreachable or returned invalid JSON. A human-readable
     diagnostic is printed to stderr.

With ``--check``:
  0  All files within caps, OR source unreachable (warned to
     stderr). Skip-on-unreachable lets CI tolerate transient network
     failures without flipping red on every blip; the result is
     visibly inconclusive rather than wrong.
  1  At least one over-cap field found; issues printed to stdout.
  2  ``--check`` was passed but PyYAML is not installed.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PUBLIC_SCHEMA_URL = "https://schema.infrahub.app/infrahub/schema/latest.json"

# Normalised output schema names (match the JSON Schema export).
SCHEMA_NAMES = ("NodeSchema", "GenericSchema",
                "AttributeSchema", "RelationshipSchema")

# Map of OpenAPI -> normalised name. The OpenAPI export uses
# `AttributeSchema-Input` for the request body variant; the JSON
# Schema export uses `AttributeSchema`. Normalise to the latter.
OPENAPI_NAME_MAP = {
    "NodeSchema": "NodeSchema",
    "GenericSchema": "GenericSchema",
    "AttributeSchema-Input": "AttributeSchema",
    "RelationshipSchema": "RelationshipSchema",
}


def fetch(url: str, timeout: float = 10.0) -> dict:
    """Fetch a JSON document from ``url`` and return the parsed dict.

    Sets a real User-Agent so CDNs that filter the default Python UA
    (some Cloudfront distributions return 403 to ``python-urllib/*``)
    still serve the response.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "infrahub-skills/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _merge_constraints(info: dict) -> dict:
    """Flatten minLength / maxLength / pattern across anyOf branches.

    Nullable fields appear as ``{"anyOf": [{"type": "string", ...},
    {"type": "null"}]}`` — the constraint sits on the string branch.
    Merging across all branches captures whichever one carries it.
    """
    merged: dict[str, int | str] = {}
    for candidate in [info] + info.get("anyOf", []):
        for key in ("minLength", "maxLength", "pattern"):
            if key in candidate and key not in merged:
                merged[key] = candidate[key]
    return merged


def _extract_properties(props: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for field, info in props.items():
        merged = _merge_constraints(info)
        if merged:
            out[field] = merged
    return out


def caps_from_json_schema(doc: dict) -> dict[str, dict[str, dict]]:
    defs = doc.get("$defs", {})
    return {
        name: _extract_properties(defs.get(name, {}).get("properties", {}))
        for name in SCHEMA_NAMES
    }


def caps_from_openapi(doc: dict) -> dict[str, dict[str, dict]]:
    schemas = doc.get("components", {}).get("schemas", {})
    out: dict[str, dict[str, dict]] = {name: {} for name in SCHEMA_NAMES}
    for openapi_name, normalised in OPENAPI_NAME_MAP.items():
        out[normalised] = _extract_properties(
            schemas.get(openapi_name, {}).get("properties", {})
        )
    return out


def check_files(paths: list[str], caps: dict[str, dict[str, dict]]) -> int:
    """Validate the named YAML files against the ``maxLength`` caps.

    Prints one ``file:Kind.field: <len> chars (max <cap>)`` line per
    over-cap field on stdout. Returns the number of issues found, or
    ``-1`` if PyYAML is not available (callers translate to exit 2).
    """
    try:
        import yaml
    except ImportError:
        print(
            "ERROR: --check requires PyYAML. Install with `pip install pyyaml`.",
            file=sys.stderr,
        )
        return -1

    issues: list[str] = []
    kind_to_schema = {"nodes": "NodeSchema", "generics": "GenericSchema"}

    def visit(ref: str, obj: dict, schema_caps: dict[str, dict]) -> None:
        for field, info in schema_caps.items():
            cap = info.get("maxLength")
            if cap is None:
                continue
            value = obj.get(field)
            if isinstance(value, str) and len(value) > cap:
                issues.append(f"{ref}.{field}: {len(value)} chars (max {cap})")

    for path_str in paths:
        path = Path(path_str)
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError) as exc:
            print(f"WARNING: could not read {path} ({exc})", file=sys.stderr)
            continue

        for kind, schema_key in kind_to_schema.items():
            for node in doc.get(kind, []) or []:
                ref = f"{path}:{node.get('namespace', '?')}{node.get('name', '?')}"
                visit(ref, node, caps.get(schema_key, {}))
                for attr in node.get("attributes", []) or []:
                    visit(f"{ref}.{attr.get('name', '?')}", attr, caps.get("AttributeSchema", {}))
                for rel in node.get("relationships", []) or []:
                    visit(f"{ref}.{rel.get('name', '?')}", rel, caps.get("RelationshipSchema", {}))

    for issue in issues:
        print(issue)
    return len(issues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group()
    src.add_argument(
        "--url",
        default=PUBLIC_SCHEMA_URL,
        help=(
            "Override the source URL. Defaults to the public JSON "
            f"Schema at {PUBLIC_SCHEMA_URL}. Use the URL of any JSON "
            "Schema document that follows the same $defs layout."
        ),
    )
    src.add_argument(
        "--openapi",
        metavar="BASE_URL",
        help=(
            "Read constraints from a running Infrahub instance's "
            "/api/openapi.json (resolved against BASE_URL) instead of "
            "the public JSON Schema. Use as a fallback when the public "
            "source is unreachable and a server has been located via "
            "connectivity-server-check.md."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Network timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--check",
        nargs="+",
        metavar="FILE",
        help=(
            "Validate the named schema YAML files against the live "
            "maxLength caps. Composes with --openapi. Exits 1 if any "
            "field is over cap; exits 0 (with stderr warning) if the "
            "source is unreachable so CI tolerates transient network "
            "failures."
        ),
    )
    args = parser.parse_args(argv)

    if args.openapi:
        url = args.openapi.rstrip("/") + "/api/openapi.json"
        from_openapi = True
    else:
        url = args.url
        from_openapi = False

    try:
        doc = fetch(url, timeout=args.timeout)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        msg = (
            f"Could not fetch {url} ({type(exc).__name__}: {exc}). "
            "String-length validation cannot be performed."
        )
        if args.check:
            # Skip-on-unreachable: CI shouldn't flip red on transient
            # network blips. The warning makes the inconclusive result
            # visible.
            print(f"WARNING: {msg}", file=sys.stderr)
            return 0
        print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    caps = caps_from_openapi(doc) if from_openapi else caps_from_json_schema(doc)

    if args.check:
        n_issues = check_files(args.check, caps)
        if n_issues < 0:
            return 2  # missing PyYAML
        return 1 if n_issues > 0 else 0

    json.dump(caps, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
