#!/usr/bin/env python3
"""Grader for the cardinality-shared-peer eval.

The fixture asks for several Services to share one Wavelength. Three of the
five checks below encode that intent, so they live here rather than in the
shared CHECKS registry: on a schema where a one-to-one pair is correct they
would be wrong.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import rels_by_identifier, run_checks  # noqa: E402

# The fixture's shared kind, the identifier both sides carry, and the
# relationship names the input schema already uses.
SHARED_KIND = "NetWavelength"
HOLDER_KIND = "NetService"
IDENTIFIER = "service__wavelength"
INPUT_NAMES = {SHARED_KIND: "service", HOLDER_KIND: "wavelength"}

_COMMENT = re.compile(r"(?:^|\s)#(.*)$")


def _entries(schema: dict) -> list[tuple[str, dict]]:
    return rels_by_identifier(schema).get(IDENTIFIER, [])


def check_shared_side_widened(schema: dict, **_: Any) -> tuple[bool, str]:
    """Exactly the Wavelength side must be `many`; the Service side stays `one`.

    The cap on how many Services may point at one Wavelength is the
    Wavelength's own declaration on this identifier. Widening
    `Service.wavelength` alone loads cleanly and leaves the cap in place, so
    an answer that only touches the Service side has to fail here.

    Widening *both* sides also lifts the cap, and is the blunt fix: it turns
    `Service.wavelength` into a list as well, changing that field's query
    shape for no reason the task asked for. Asserting only the shared side
    scored the blunt answer identically to the correct one, which made the
    rule's central point -- which side actually caps -- the one thing the
    eval could not see.
    """
    owned = [rel for kind, rel in _entries(schema) if kind == SHARED_KIND]
    if not owned:
        return False, f"{SHARED_KIND} declares nothing on identifier {IDENTIFIER!r}"
    shared_cardinalities = [str(rel.get("cardinality", "<unset>")) for rel in owned]
    if "many" not in shared_cardinalities:
        return False, (
            f"{SHARED_KIND} side is cardinality {shared_cardinalities}; the inbound "
            f"cap lives here, so widening only {HOLDER_KIND} does not lift it"
        )

    held = [rel for kind, rel in _entries(schema) if kind == HOLDER_KIND]
    if not held:
        return False, f"{HOLDER_KIND} declares nothing on identifier {IDENTIFIER!r}"
    holder_cardinalities = [str(rel.get("cardinality", "<unset>")) for rel in held]
    # `cardinality` defaults to `many` when unset, so an omitted key on the
    # holder side is a widening too.
    if any(c in ("many", "<unset>") for c in holder_cardinalities):
        return False, (
            f"{HOLDER_KIND} side is cardinality {holder_cardinalities}; a service "
            "still has one wavelength, so widening this side too turns "
            f"{HOLDER_KIND}.wavelength into a list and changes that field's query "
            "shape for nothing the task asked for"
        )
    return True, (
        f"{SHARED_KIND} side is many and {HOLDER_KIND} side is still one, so the "
        "cap is lifted on exactly the side that held it"
    )


def check_relationship_names_unchanged(schema: dict, **_: Any) -> tuple[bool, str]:
    """The widened relationship keeps the singular name the input gave it.

    Renaming to a plural in the same change leaves two declarations on one
    identifier and is rejected at load. A rename that replaces the old
    declaration in place loads fine, so nothing but this check catches it.
    """
    by_kind: dict[str, list[str]] = {}
    for kind, rel in _entries(schema):
        by_kind.setdefault(kind, []).append(str(rel.get("name", "?")))
    problems = []
    for kind, expected in INPUT_NAMES.items():
        found = by_kind.get(kind, [])
        if expected not in found:
            problems.append(f"{kind} no longer declares {expected!r} (has {found})")
    if problems:
        return False, "; ".join(problems)
    return True, "both relationships keep their original singular names"


def check_comments_cover_query_migration(
    schema: dict, raw_text: str = "", **_: Any
) -> tuple[bool, str]:
    """The blast radius must be stated in YAML comments.

    The task asks for it in comments, which the YAML parser discards, so this
    reads the raw file instead of the parsed schema.
    """
    comments = " ".join(
        m.group(1) for line in (raw_text or "").splitlines() if (m := _COMMENT.search(line))
    ).lower()
    if not comments.strip():
        return False, "output carries no YAML comments"
    missing = []
    # The two shapes have to be contrasted, not merely mentioned: a bare
    # "# node edges query" was passing this check.
    if not re.search(r"edges\b[^\n]{0,80}\bnode\b|\bnode\b[^\n]{0,80}edges\b", comments):
        missing.append(
            "the selection-shape change, as the contrast between the one-side "
            "`node { ... }` and the many-side `edges { node { ... } }`"
        )
    if not any(term in comments for term in ("quer", ".gql", "graphql")):
        missing.append("the stored-query impact")
    # And the failure a reader will actually see, which is the point of
    # writing the migration down before making it.
    if not re.search(
        r"nested\s*edged|nested\s*paginated|not valid|import[- ]?time|error", comments
    ):
        missing.append(
            "the failure it produces (the NestedEdged / NestedPaginated field "
            "error, or the import-time `Query is not valid` failure)"
        )
    if missing:
        return False, "comments do not mention " + "; ".join(missing)
    return True, "comments contrast both selection shapes and name the failure"


CHECKS = [
    "schema-version",
    ("shared-side-widened", check_shared_side_widened),
    ("relationship-names-unchanged", check_relationship_names_unchanged),
    "identifier-unique-per-direction",
    "many-max-count-valid",
    "matching-identifiers",
    ("comments-cover-query-migration", check_comments_cover_query_migration),
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.yml"))))
