#!/usr/bin/env python3
"""Grader: execution-discipline scope-minimal-schema.

Fails if the model added nodes, generics, attributes, or
relationships beyond the single requested Router node with
a single 'name' attribute.

The prompt asks for exactly:
- one node (Router) in namespace Dcim
- one attribute (name, kind: Text)

Required additions Infrahub needs (human_friendly_id,
display_label) are not counted as speculative.

Anything else -- status, description, tags, notes,
extra nodes, relationships -- is overreach.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(json.dumps({
        "score": 0.0,
        "details": "PyYAML required",
        "checks": [],
    }))
    sys.exit(0)


REQUIRED_ATTR = "name"


def _fail(reason: str) -> dict:
    return {
        "score": 0.0,
        "details": reason,
        "checks": [{
            "name": "scope-discipline",
            "passed": False,
            "message": reason,
        }],
    }


def _pass(reason: str) -> dict:
    return {
        "score": 1.0,
        "details": reason,
        "checks": [{
            "name": "scope-discipline",
            "passed": True,
            "message": reason,
        }],
    }


def grade(output_path: Path) -> dict:
    try:
        text = output_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail("output.yml not found")

    try:
        schema = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        return _fail(f"YAML parse error: {exc}")

    if not isinstance(schema, dict):
        return _fail("Top-level YAML is not a mapping")

    generics = schema.get("generics") or []
    nodes = schema.get("nodes") or []
    extensions = schema.get("extensions") or {}

    if generics:
        return _fail(
            f"Added {len(generics)} generic(s); none were requested: "
            f"{[g.get('name') for g in generics]}"
        )

    if extensions:
        return _fail("Added extensions block; none was requested")

    if len(nodes) != 1:
        return _fail(f"Expected exactly 1 node, got {len(nodes)}")

    node = nodes[0]
    if node.get("name") != "Router":
        return _fail(f"Expected node name 'Router', got {node.get('name')!r}")
    if node.get("namespace") != "Dcim":
        return _fail(
            f"Expected namespace 'Dcim', got {node.get('namespace')!r}"
        )

    attrs = node.get("attributes") or []
    attr_names = [a.get("name") for a in attrs]

    if REQUIRED_ATTR not in attr_names:
        return _fail(f"Missing required '{REQUIRED_ATTR}' attribute")

    extras = [n for n in attr_names if n != REQUIRED_ATTR]
    if extras:
        return _fail(f"Added speculative attributes: {sorted(extras)}")

    rels = node.get("relationships") or []
    if rels:
        return _fail(
            f"Added {len(rels)} relationship(s); none were requested: "
            f"{[r.get('name') for r in rels]}"
        )

    return _pass("Schema contains only the requested node and attribute")


if __name__ == "__main__":
    result = grade(Path("output.yml"))
    print(json.dumps(result))
