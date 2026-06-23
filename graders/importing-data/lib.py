"""Shared grader library for infrahub-importing-data skill evaluations.

The CSV-import skill emits a *directory* of YAML object files (one per kind,
NN-prefixed for load order) rather than a single file. The checks here walk
the emitted directory, parse each YAML document, and assert shape against
the rules defined in ``skills/infrahub-importing-data/rules/``.

A small fixture schema is embedded so two checks (``dropdown-names`` and
``hfid-reference-shape``) can reason about kinds without round-tripping
through Infrahub. The fixture mirrors the schema that the eval prompt
declares inline; if the prompt changes, update both together.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["envelope", "load-order-numbering"],
        Path("./output_dir"),
    )
    print(result)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# Fixture schema
#
# Mirrors the inline schema the eval prompts declare. Keep in sync with the
# task prompts in ``eval.yaml``.
# ---------------------------------------------------------------------------


# Dropdown choices keyed by ``(kind, attribute_name)`` → set of *label*
# strings the skill must NOT emit (it should emit the matching ``name``).
FIXTURE_DROPDOWN_LABELS: dict[tuple[str, str], set[str]] = {
    ("DcimDevice", "status"): {"Active", "Maintenance", "Retired", "Decommissioned"},
}

# Dropdown choices keyed by ``(kind, attribute_name)`` → set of valid
# ``name`` strings. Used to detect when the skill correctly emitted a name.
FIXTURE_DROPDOWN_NAMES: dict[tuple[str, str], set[str]] = {
    ("DcimDevice", "status"): {"active", "maintenance", "retired", "decommissioned"},
}

# HFID length per kind. 1 → scalar reference; >1 → list reference.
FIXTURE_HFID_LENGTH: dict[str, int] = {
    "OrganizationManufacturer": 1,
    "LocationSite": 1,
    "DcimDevice": 1,
    "DcimDeviceType": 1,
    "DcimPlatform": 1,
    "DcimRack": 1,
    "DcimRoom": 2,  # site__shortname__value + name__value
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _docs_from_file(text: str) -> list[dict]:
    """Parse a (possibly multi-document) YAML file into a list of dicts.

    Empty / non-mapping documents are dropped. Parse errors return an empty
    list (the envelope check will catch missing structure).
    """
    try:
        loaded = list(yaml.safe_load_all(text))
    except yaml.YAMLError:
        return []
    return [doc for doc in loaded if isinstance(doc, dict)]


def load_output_dir(path: Path) -> dict[Path, list[dict]]:
    """Walk ``path`` and return ``{file_path: [parsed_docs, ...]}``.

    If ``path`` is missing or empty, returns an empty dict. Files that fail
    YAML parsing map to an empty list (so the envelope check fails them).
    """
    parsed: dict[Path, list[dict]] = {}
    if not path.exists() or not path.is_dir():
        return parsed

    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        try:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            parsed[file_path] = []
            continue
        parsed[file_path] = _docs_from_file(raw)
    return parsed


# ---------------------------------------------------------------------------
# Individual check functions
#
# Each check has the signature:
#     check_*(parsed_files: dict, *, output_dir: Path, **kwargs) -> tuple[bool, str]
# ---------------------------------------------------------------------------


def check_envelope(parsed_files: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Every emitted YAML document is a well-formed Object envelope.

    Required fields: ``apiVersion``, ``kind: Object``, ``spec.kind``,
    ``spec.data`` (a list).
    """
    if not parsed_files:
        return False, "No YAML files found in output directory"

    issues: list[str] = []
    total_docs = 0
    for file_path, docs in parsed_files.items():
        if not docs:
            issues.append(f"{file_path.name}: no parseable YAML documents")
            continue
        for idx, doc in enumerate(docs):
            total_docs += 1
            ref = f"{file_path.name}[doc {idx}]"
            if not doc.get("apiVersion"):
                issues.append(f"{ref}: missing apiVersion")
            if doc.get("kind") != "Object":
                issues.append(f"{ref}: kind is {doc.get('kind')!r}, expected 'Object'")
            spec = doc.get("spec")
            if not isinstance(spec, dict):
                issues.append(f"{ref}: missing or non-mapping spec")
                continue
            if not spec.get("kind"):
                issues.append(f"{ref}: missing spec.kind")
            data = spec.get("data")
            if not isinstance(data, list):
                issues.append(f"{ref}: spec.data is not a list")

    if issues:
        return False, "; ".join(issues[:6])
    return True, f"All {total_docs} documents have a valid Object envelope"


_NN_PREFIX_RE = re.compile(r"^(\d+)[a-z]?_")


def check_load_order_numbering(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Every YAML file uses an ``NN_`` numeric prefix and dependent files load later.

    Heuristic for "depends on": if file A's ``spec.data`` references a kind
    via relationship name and that referenced kind is emitted by file B,
    then B's NN must be <= A's NN.
    """
    if not parsed_files:
        return False, "No YAML files to inspect"

    missing_prefix: list[str] = []
    file_to_num: dict[Path, int] = {}
    kind_to_min_file: dict[str, Path] = {}
    file_to_kinds: dict[Path, set[str]] = {}

    for file_path, docs in parsed_files.items():
        m = _NN_PREFIX_RE.match(file_path.name)
        if not m:
            missing_prefix.append(file_path.name)
            continue
        num = int(m.group(1))
        file_to_num[file_path] = num
        kinds_in_file: set[str] = set()
        for doc in docs:
            spec = doc.get("spec") or {}
            k = spec.get("kind")
            if isinstance(k, str):
                kinds_in_file.add(k)
                # Track the earliest file producing this kind.
                prev = kind_to_min_file.get(k)
                if prev is None or file_to_num.get(prev, num) > num:
                    kind_to_min_file[k] = file_path
        file_to_kinds[file_path] = kinds_in_file

    if missing_prefix:
        return False, (
            f"Files missing NN_ numeric prefix: {', '.join(sorted(missing_prefix))}"
        )

    # Heuristic dependency check: if a data row references a value that is
    # the HFID-bearing scalar of a kind emitted elsewhere, that producer
    # file must have a <= prefix. We approximate "references a kind" by
    # looking for relationship-shaped scalar/list values matching emitted
    # kinds' object names. Because emitted YAML uses HFID strings (not
    # kinds), a strict mapping isn't possible without the schema — so we
    # require only that the file names are sortable and globally
    # monotonic-ish: each kind is produced in exactly one file.
    duplicate_kinds: list[str] = []
    kinds_seen: dict[str, Path] = {}
    for file_path, kinds in file_to_kinds.items():
        for k in kinds:
            prev = kinds_seen.get(k)
            if prev is not None and prev != file_path:
                duplicate_kinds.append(f"{k} in both {prev.name} and {file_path.name}")
            kinds_seen[k] = file_path

    if duplicate_kinds:
        return False, "Same kind emitted in multiple files: " + "; ".join(duplicate_kinds[:4])

    return True, f"All {len(file_to_num)} files use NN_ prefixes; each kind has one producer"


def _walk_data_rows(parsed_files: dict[Path, list[dict]]):
    """Yield ``(file_path, kind, row_dict)`` tuples for every data entry.

    Skips non-mapping rows.
    """
    for file_path, docs in parsed_files.items():
        for doc in docs:
            spec = doc.get("spec") or {}
            kind = spec.get("kind")
            data = spec.get("data") or []
            if not isinstance(data, list):
                continue
            for row in data:
                if isinstance(row, dict):
                    yield file_path, kind, row


def check_dropdown_names(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Dropdown attribute values must be choice ``name``s, not labels.

    Uses the embedded ``FIXTURE_DROPDOWN_LABELS`` table to detect when a
    known dropdown attribute carries a label-style string (e.g.,
    ``"Active"`` instead of ``"active"``).
    """
    violations: list[str] = []
    inspected = 0
    for file_path, kind, row in _walk_data_rows(parsed_files):
        if not isinstance(kind, str):
            continue
        for attr_name, value in row.items():
            key = (kind, attr_name)
            labels = FIXTURE_DROPDOWN_LABELS.get(key)
            if not labels:
                continue
            inspected += 1
            # Allow value+metadata mapping form: {"value": "active", ...}
            if isinstance(value, dict):
                value = value.get("value")
            if isinstance(value, str) and value in labels:
                violations.append(f"{file_path.name}: {kind}.{attr_name}={value!r}")

    if violations:
        return False, "Dropdown values use labels not names: " + "; ".join(violations[:6])
    if inspected == 0:
        return False, "No known dropdown attributes appeared in any emitted row"
    return True, f"All {inspected} known dropdown values use choice names (not labels)"


# Relationship-like keys are heuristic: names that aren't typical attribute
# slots and aren't envelope/structural keys.
_STRUCTURAL_KEYS = {
    "apiVersion",
    "kind",
    "spec",
    "data",
    "parameters",
    "expand_range",
}


def _is_relationship_ref(value: Any) -> bool:
    """A relationship reference is either a scalar HFID, list HFID, or a
    component-children mapping (``{kind, data: [...]}``)."""
    if isinstance(value, (str, int, float)):
        return True
    if isinstance(value, list):
        # A list of scalars (HFID parts) is a reference; a list of dicts
        # is a component children block written incorrectly.
        return all(isinstance(v, (str, int, float)) for v in value) and bool(value)
    if isinstance(value, dict):
        return "kind" in value and "data" in value
    return False


def check_hfid_reference_shape(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Relationship references match target HFID arity.

    Single-element HFID → scalar reference (``site: par-1``).
    Multi-element HFID → list reference of length == HFID length
    (``room: ["par-1", "rack-01"]``).
    """
    issues: list[str] = []
    inspected = 0
    for file_path, _kind, row in _walk_data_rows(parsed_files):
        for key, value in row.items():
            # Skip non-relationship slots (component children handled separately).
            if isinstance(value, dict) and "data" in value and "kind" in value:
                continue
            # Detect when ``key`` names a known reference target kind.
            # We rely on a heuristic: if any FIXTURE_HFID_LENGTH key is
            # spelled close to the relationship key, use that.
            target_kind = _guess_target_kind(key)
            if not target_kind or target_kind not in FIXTURE_HFID_LENGTH:
                continue
            expected_len = FIXTURE_HFID_LENGTH[target_kind]
            inspected += 1
            actual_value = value
            if isinstance(actual_value, dict):
                actual_value = actual_value.get("value", actual_value)
            if expected_len == 1:
                if isinstance(actual_value, list):
                    issues.append(
                        f"{file_path.name}: {key} should be scalar HFID for {target_kind} "
                        f"(HFID length 1), got list of {len(actual_value)}"
                    )
            else:  # expected_len > 1
                if not isinstance(actual_value, list):
                    issues.append(
                        f"{file_path.name}: {key} should be list HFID of length "
                        f"{expected_len} for {target_kind}, got scalar"
                    )
                elif len(actual_value) != expected_len:
                    issues.append(
                        f"{file_path.name}: {key} list HFID has {len(actual_value)} "
                        f"elements, expected {expected_len} for {target_kind}"
                    )

    if issues:
        return False, "; ".join(issues[:5])
    if inspected == 0:
        return True, "No known reference targets appeared (vacuously passes)"
    return True, f"All {inspected} relationship references match target HFID arity"


# Relationship-name → target kind guesses for the fixture schema.
_REL_NAME_TO_KIND = {
    "manufacturer": "OrganizationManufacturer",
    "site": "LocationSite",
    "device": "DcimDevice",
    "device_type": "DcimDeviceType",
    "platform": "DcimPlatform",
    "rack": "DcimRack",
    "room": "DcimRoom",
}


def _guess_target_kind(rel_name: str) -> str | None:
    return _REL_NAME_TO_KIND.get(rel_name)


def check_component_children_shape(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Component children use ``<rel>: {kind, data: [...]}`` not a bare list.

    Detects the antipattern where a relationship key is set to a bare list
    of dicts (children rows) instead of the wrapper mapping that supplies
    the concrete child kind.
    """
    issues: list[str] = []
    wrapped_count = 0
    for file_path, _kind, row in _walk_data_rows(parsed_files):
        for key, value in row.items():
            # Detect a bare list of dicts under a non-structural key.
            if key in _STRUCTURAL_KEYS:
                continue
            if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
                # Distinguish bare children-list from list-of-HFID-parts:
                # children dicts have multiple keys; HFID parts are
                # scalars (already excluded above).
                issues.append(
                    f"{file_path.name}: {key} is a bare list of dicts; "
                    f"wrap as {{kind: <ChildKind>, data: [...]}}"
                )
            elif isinstance(value, dict) and "data" in value:
                if "kind" not in value:
                    issues.append(
                        f"{file_path.name}: {key} children mapping missing 'kind'"
                    )
                elif not isinstance(value.get("data"), list):
                    issues.append(
                        f"{file_path.name}: {key} children mapping 'data' is not a list"
                    )
                else:
                    wrapped_count += 1

    if issues:
        return False, "; ".join(issues[:5])
    if wrapped_count == 0:
        return True, "No component children present (vacuously passes)"
    return True, f"All {wrapped_count} component-children mappings use {{kind, data}}"


_RANGE_PATTERN = re.compile(r"\[\d+\s*-\s*\d+\]")


def check_range_expansion(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """If any child row name uses bracket-range syntax, the enclosing
    relationship block must set ``parameters.expand_range: true``."""
    issues: list[str] = []
    matched = 0
    for file_path, _kind, row in _walk_data_rows(parsed_files):
        for key, value in row.items():
            if not (isinstance(value, dict) and "data" in value):
                continue
            children = value.get("data") or []
            if not isinstance(children, list):
                continue
            has_range = any(
                isinstance(child, dict)
                and isinstance(child.get("name"), str)
                and _RANGE_PATTERN.search(child["name"])
                for child in children
            )
            if not has_range:
                continue
            params = value.get("parameters") or {}
            if not isinstance(params, dict) or params.get("expand_range") is not True:
                issues.append(
                    f"{file_path.name}: {key} has bracket-range names but "
                    f"parameters.expand_range is not true"
                )
            else:
                matched += 1

    if issues:
        return False, "; ".join(issues[:5])
    if matched == 0:
        return True, "No bracket-range names emitted (vacuously passes)"
    return True, f"All {matched} bracket-range blocks set parameters.expand_range: true"


def check_no_schema_mutation(
    parsed_files: dict[Path, list[dict]],
    *,
    output_dir: Path | None = None,
    **_: Any,
) -> tuple[bool, str]:
    """Within the emitted output dir, no file is a schema document.

    A schema document is identifiable by top-level ``version: "1.0"`` plus
    ``nodes:`` or ``generics:`` keys. Also fails if any file lives under a
    ``schemas/`` sub-path inside the emission directory.
    """
    if not parsed_files:
        return False, "No YAML files in output directory"

    base = output_dir.resolve() if output_dir else None
    violations: list[str] = []
    for file_path, docs in parsed_files.items():
        # Check sub-path
        if base is not None:
            try:
                rel = file_path.resolve().relative_to(base)
                if "schemas" in rel.parts:
                    violations.append(f"{file_path} lives under a schemas/ sub-path")
            except ValueError:
                pass
        for doc in docs:
            version = doc.get("version")
            has_schema_keys = "nodes" in doc or "generics" in doc
            if version == "1.0" and has_schema_keys:
                violations.append(
                    f"{file_path.name}: schema document (version 1.0 + nodes/generics)"
                )
                break

    if violations:
        return False, "; ".join(violations[:5])
    return True, "No schema mutation in emitted output dir"


# ---------------------------------------------------------------------------
# Fixture for value-coercion: attribute kinds per (kind, attribute_name)
# ---------------------------------------------------------------------------


# Per-attribute expected YAML value-type after coercion. Keep in sync with the
# eval prompt's inline schema.
FIXTURE_ATTRIBUTE_KIND: dict[tuple[str, str], str] = {
    ("DcimDevice", "is_managed"): "Boolean",
    ("DcimDevice", "gpu_count"): "Number",
    ("DcimDevice", "commissioned_at"): "DateTime",
    ("DcimDevice", "metadata"): "JSON",
}


# Attribute optionality fixture for empty/null check.
FIXTURE_OPTIONAL: dict[tuple[str, str], bool] = {
    ("OrganizationManufacturer", "name"): False,
    ("OrganizationManufacturer", "description"): True,
    ("OrganizationManufacturer", "country"): True,
}


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:?\d{2})?)?$")


def _attr_value(value: Any) -> Any:
    """Return the underlying scalar from either a plain cell or a
    value+metadata mapping."""
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def check_value_coercion(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Boolean / Number / DateTime / JSON attributes carry native YAML values.

    A Boolean cell must emit `true` or `false` (YAML bool), not the strings
    `"Yes"` / `"true"`. Number must emit int/float, not a numeric string.
    DateTime must emit an ISO-8601-shaped string. JSON must emit a parsed
    structure, not a JSON-encoded string.
    """
    issues: list[str] = []
    inspected = 0
    for file_path, kind, row in _walk_data_rows(parsed_files):
        if not isinstance(kind, str):
            continue
        for attr_name, raw in row.items():
            expected = FIXTURE_ATTRIBUTE_KIND.get((kind, attr_name))
            if not expected:
                continue
            inspected += 1
            value = _attr_value(raw)
            if expected == "Boolean":
                if not isinstance(value, bool):
                    issues.append(
                        f"{file_path.name}: {kind}.{attr_name}={value!r} "
                        f"is not a YAML boolean"
                    )
            elif expected == "Number":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    issues.append(
                        f"{file_path.name}: {kind}.{attr_name}={value!r} "
                        f"is not a YAML number"
                    )
            elif expected == "DateTime":
                if not (isinstance(value, str) and _ISO_DATE_RE.match(value)):
                    issues.append(
                        f"{file_path.name}: {kind}.{attr_name}={value!r} "
                        f"is not an ISO-8601 string"
                    )
            elif expected == "JSON":
                if not isinstance(value, (dict, list)):
                    issues.append(
                        f"{file_path.name}: {kind}.{attr_name}={value!r} "
                        f"is not a parsed JSON structure"
                    )

    if issues:
        return False, "; ".join(issues[:6])
    if inspected == 0:
        return False, "No known typed attributes appeared in any emitted row"
    return True, f"All {inspected} typed attribute values coerced correctly"


def check_empty_and_null(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Blank optional cells are omitted; blank required cells fail closed.

    Verifies (a) no emitted attribute carries the empty string, (b) optional
    attributes that are blank in the source are absent from the row, (c) no
    YAML `null` literal appears on a known attribute.
    """
    issues: list[str] = []
    inspected = 0
    for file_path, kind, row in _walk_data_rows(parsed_files):
        if not isinstance(kind, str):
            continue
        for attr_name, raw in row.items():
            if (kind, attr_name) not in FIXTURE_OPTIONAL:
                continue
            inspected += 1
            value = _attr_value(raw)
            if value is None:
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name} is null "
                    f"(omit the attribute instead of emitting null)"
                )
            elif isinstance(value, str) and value == "":
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name} is empty string "
                    f"(omit the attribute instead)"
                )

    if issues:
        return False, "; ".join(issues[:6])
    if inspected == 0:
        return True, "No fixture-tracked attributes appeared (vacuously passes)"
    return True, f"All {inspected} fixture attributes use omit-on-blank semantics"


def check_csv_dialect(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """A semicolon-delimited / BOM / non-UTF-8 source still emits clean values.

    Detection criteria: every name-bearing attribute in the emission is
    free of stray delimiter / BOM bytes. The grader doesn't see the source,
    so it asserts the *output* shape — a row whose `name` contains `;` or
    `\\ufeff` indicates a dialect that wasn't parsed correctly.
    """
    issues: list[str] = []
    inspected = 0
    for file_path, _kind, row in _walk_data_rows(parsed_files):
        for attr_name, raw in row.items():
            value = _attr_value(raw)
            if not isinstance(value, str):
                continue
            inspected += 1
            if "﻿" in value:
                issues.append(
                    f"{file_path.name}: {attr_name}={value!r} contains a BOM "
                    f"byte (dialect detection missed UTF-8 BOM)"
                )
            elif ";" in value and value.count(";") >= 2:
                issues.append(
                    f"{file_path.name}: {attr_name}={value!r} contains multiple "
                    f"semicolons (file was read as comma-delimited)"
                )

    if issues:
        return False, "; ".join(issues[:6])
    if inspected == 0:
        return False, "No string attributes appeared in any emitted row"
    return True, f"All {inspected} string values are dialect-clean"


def check_pre_flight_closure(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Every relationship reference resolves to an emitted row in the dir.

    For every row, look at relationship-shaped values (scalars and lists
    that aren't attribute scalars). If the referenced name doesn't appear
    as `name` of any row whose `kind` matches the relationship's expected
    target, flag it as an orphan.
    """
    # Build set of emitted (kind, name) pairs.
    emitted: dict[str, set[str]] = {}
    for _file_path, kind, row in _walk_data_rows(parsed_files):
        if not isinstance(kind, str):
            continue
        name_value = _attr_value(row.get("name"))
        if isinstance(name_value, str):
            emitted.setdefault(kind, set()).add(name_value)

    issues: list[str] = []
    inspected = 0
    for file_path, _kind, row in _walk_data_rows(parsed_files):
        for key, value in row.items():
            target_kind = _guess_target_kind(key)
            if not target_kind:
                continue
            actual = _attr_value(value)
            if isinstance(actual, dict) and "data" in actual:
                continue  # component children block, not a reference
            if isinstance(actual, list):
                if not actual or not all(isinstance(v, (str, int, float)) for v in actual):
                    continue
                # multi-element HFID: first element typically distinguishes; skip closure check
                continue
            if not isinstance(actual, str):
                continue
            inspected += 1
            targets = emitted.get(target_kind, set())
            if actual not in targets:
                issues.append(
                    f"{file_path.name}: {key}={actual!r} references "
                    f"{target_kind} but no row with that name was emitted"
                )

    if issues:
        return False, "; ".join(issues[:5])
    if inspected == 0:
        return True, "No cross-file references emitted (vacuously passes)"
    return True, f"All {inspected} references resolve to emitted rows"


# ---------------------------------------------------------------------------
# Fixture for column-to-attribute mapping
# ---------------------------------------------------------------------------


# Allowed attribute names per kind. Anything outside this set on an emitted
# row indicates the mapping ladder invented an attribute (schema mutation by
# stealth) or skipped the snake_case round-trip step.
FIXTURE_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "DcimDevice": {
        "name",
        "memory_gb",
        "cpu_count",
        "rack_unit_position",
        "role",
        "status",
        "platform",
        "site",
        "manufacturer",
        "device_type",
    },
    "OrganizationManufacturer": {"name", "description", "country"},
    "LocationSite": {"name", "shortname"},
}


# Attribute names that should NEVER appear (silent unit-rename artifacts).
FIXTURE_FORBIDDEN_ATTRIBUTES: set[str] = {"memory_tb", "memory_kb", "memory_mb"}


_RAW_HEADER_CHARS = set(" ()/")


def check_column_to_attribute(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Emitted attribute names come from the schema, not the raw CSV header.

    Verifies (a) every attribute on every emitted row is in the fixture's
    allowed set for its kind, (b) no forbidden unit-rename attribute name
    appears, (c) no raw-header artifacts (spaces, parens, slashes) survive
    on attribute names.
    """
    issues: list[str] = []
    inspected = 0
    for file_path, kind, row in _walk_data_rows(parsed_files):
        if not isinstance(kind, str):
            continue
        allowed = FIXTURE_ALLOWED_ATTRIBUTES.get(kind)
        for attr_name in row.keys():
            inspected += 1
            if any(c in _RAW_HEADER_CHARS for c in attr_name):
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name!r} retains raw "
                    f"header characters (snake_case round-trip skipped)"
                )
                continue
            if attr_name in FIXTURE_FORBIDDEN_ATTRIBUTES:
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name!r} is a "
                    f"unit-rename of a schema attribute (silently bound)"
                )
                continue
            if allowed is not None and attr_name not in allowed:
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name!r} is not in the "
                    f"schema's attribute list for {kind}"
                )

    if issues:
        return False, "; ".join(issues[:6])
    if inspected == 0:
        return False, "No emitted rows to inspect for attribute names"
    return True, f"All {inspected} attribute names map cleanly to the schema"


# ---------------------------------------------------------------------------
# Fixture for merge-same-kind
# ---------------------------------------------------------------------------


# Expected unique-row count per merged kind when two inputs are joined.
# The check counts rows in the single emitted file for the kind and verifies
# it matches.
FIXTURE_MERGE_EXPECTED_ROWS: dict[str, int] = {
    "OrganizationManufacturer": 6,
}


def check_merge_same_kind(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Two same-kind input CSVs collapse into one file with all rows.

    For each kind in ``FIXTURE_MERGE_EXPECTED_ROWS``: exactly one emitted
    file produces that kind, and its ``spec.data`` covers the expected
    merged row count (after dedup).
    """
    # Group rows by kind across all files.
    rows_per_kind: dict[str, list] = {}
    files_per_kind: dict[str, set[Path]] = {}
    for file_path, kind, row in _walk_data_rows(parsed_files):
        if not isinstance(kind, str):
            continue
        rows_per_kind.setdefault(kind, []).append(row)
        files_per_kind.setdefault(kind, set()).add(file_path)

    issues: list[str] = []
    for kind, expected_count in FIXTURE_MERGE_EXPECTED_ROWS.items():
        files = files_per_kind.get(kind) or set()
        rows = rows_per_kind.get(kind) or []
        if len(files) == 0:
            issues.append(f"{kind}: no emitted file produces this kind")
            continue
        if len(files) > 1:
            names = sorted(f.name for f in files)
            issues.append(
                f"{kind}: emitted across {len(files)} files "
                f"({', '.join(names)}); same-kind inputs should merge"
            )
            continue
        if len(rows) < expected_count:
            issues.append(
                f"{kind}: emitted {len(rows)} rows, expected at least "
                f"{expected_count} (both inputs merged + deduped)"
            )

    if issues:
        return False, "; ".join(issues[:5])
    return True, "Same-kind inputs merged into one file per kind"


# ---------------------------------------------------------------------------
# Fixture for lineage stamping
# ---------------------------------------------------------------------------


# Expected source tag the user opted in to in the eval prompt.
FIXTURE_LINEAGE_TAG = "csv-import-20260622"


def check_lineage_stamping(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Opt-in lineage stamps every value with the expected source tag.

    For every emitted row, every attribute must be a mapping with both
    ``value:`` and ``source:`` keys, and ``source:`` must match the
    fixture's expected import tag.
    """
    issues: list[str] = []
    inspected = 0
    stamped = 0
    for file_path, kind, row in _walk_data_rows(parsed_files):
        for attr_name, raw in row.items():
            # Skip relationship children blocks ({kind, data: [...]})
            if isinstance(raw, dict) and "data" in raw and "kind" in raw:
                continue
            # Skip pure scalar references that aren't attributes (heuristic:
            # the value is a list of HFID parts)
            if isinstance(raw, list):
                continue
            inspected += 1
            if not isinstance(raw, dict):
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name} is a plain scalar "
                    f"(opt-in lineage requires value+metadata form)"
                )
                continue
            if "value" not in raw:
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name} mapping is missing "
                    f"`value:` key"
                )
                continue
            source = raw.get("source")
            if source != FIXTURE_LINEAGE_TAG:
                issues.append(
                    f"{file_path.name}: {kind}.{attr_name} source={source!r} "
                    f"(expected {FIXTURE_LINEAGE_TAG!r})"
                )
                continue
            stamped += 1

    if issues:
        return False, "; ".join(issues[:6])
    if inspected == 0:
        return False, "No attribute values to inspect for lineage stamping"
    return True, f"All {stamped} attribute values stamped with the expected source"


_PROVENANCE_RE = re.compile(
    r"(?m)^#\s*Generated by\s+infrahub-importing-data\b"
)
_PROVENANCE_SOURCES_RE = re.compile(r"(?m)^#\s*Sources?:")


def check_provenance_comment(
    parsed_files: dict[Path, list[dict]], *, output_dir: Path | None = None, **_: Any
) -> tuple[bool, str]:
    """Every emitted YAML file starts with the provenance comment block."""
    if not parsed_files:
        return False, "No YAML files in output directory"

    missing: list[str] = []
    for file_path in parsed_files.keys():
        try:
            head = file_path.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            missing.append(f"{file_path.name}: unreadable")
            continue
        if not _PROVENANCE_RE.search(head):
            missing.append(f"{file_path.name}: missing 'Generated by infrahub-importing-data' header")
            continue
        if not _PROVENANCE_SOURCES_RE.search(head):
            missing.append(f"{file_path.name}: missing 'Sources:' line")

    if missing:
        return False, "; ".join(missing[:5])
    return True, f"All {len(parsed_files)} files carry the provenance comment"


def check_fail_closed(
    parsed_files: dict[Path, list[dict]],
    *,
    output_dir: Path | None = None,
    **_: Any,
) -> tuple[bool, str]:
    """Fail-closed on an unmapped column: no object data is emitted.

    When an input column has no schema home, the skill must stop and write
    nothing — never a partial emission that silently drops the column. The
    grader asserts the invariant that survives in the output directory: no
    Object-envelope document carries any ``spec.data`` rows. A plain-text
    report explaining the unmapped column is fine (it isn't a YAML Object),
    and an empty / absent output dir also passes.
    """
    offending: list[str] = []
    for file_path, docs in parsed_files.items():
        for idx, doc in enumerate(docs):
            if doc.get("kind") != "Object":
                continue
            spec = doc.get("spec")
            data = spec.get("data") if isinstance(spec, dict) else None
            if isinstance(data, list) and len(data) > 0:
                offending.append(
                    f"{file_path.name}[doc {idx}]: emitted {len(data)} object row(s)"
                )

    if offending:
        return (
            False,
            "Did not fail closed — object data was written for an input with an "
            "unmapped column: " + "; ".join(offending[:5]),
        )
    return True, "Failed closed — no object rows emitted for the unmapped column"


# Kinds the folder-coverage eval's input directory implies. Every one must
# appear in the emission — a missing kind means a CSV was silently dropped
# during folder expansion. Keep in sync with the eval prompt.
FIXTURE_FOLDER_EXPECTED_KINDS: set[str] = {
    "OrganizationManufacturer",
    "LocationSite",
    "DcimDevice",
}


def check_folder_coverage(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Every input file in a folder / list contributes to the emission.

    Folder and multi-path inputs normalize to a flat file list, so each
    distinct kind the input implies must show up in the output. A missing
    kind means a file was dropped during expansion rather than profiled.
    Emitted files must also be NN-prefixed so load order is explicit.
    """
    if not parsed_files:
        return False, "No YAML files in output directory"

    emitted_kinds: set[str] = set()
    for _file_path, kind, _row in _walk_data_rows(parsed_files):
        if isinstance(kind, str):
            emitted_kinds.add(kind)

    missing = sorted(FIXTURE_FOLDER_EXPECTED_KINDS - emitted_kinds)
    if missing:
        return (
            False,
            f"Input file(s) dropped during expansion — no rows for: {', '.join(missing)}",
        )

    unnumbered = [fp.name for fp in parsed_files if not _NN_PREFIX_RE.match(fp.name)]
    if unnumbered:
        return (
            False,
            f"Emitted files lack an NN_ load-order prefix: {', '.join(unnumbered[:5])}",
        )

    return (
        True,
        f"All {len(FIXTURE_FOLDER_EXPECTED_KINDS)} input kinds emitted; files NN-prefixed",
    )


# ---------------------------------------------------------------------------
# Fixture for denormalized-sheet decomposition
# ---------------------------------------------------------------------------


# A single denormalized sheet conflating these kinds must split into one
# NN-prefixed file per kind. Keep in sync with the eval prompt.
FIXTURE_DECOMP_EXPECTED_KINDS: set[str] = {
    "OrganizationManufacturer",
    "LocationSite",
    "DcimDevice",
}

# Reference relationships the referring kind carries into upstream kinds. The
# producer file of the target kind must load no later than the file holding a
# row that references it.
FIXTURE_DECOMP_REFERENCES: dict[str, str] = {
    "manufacturer": "OrganizationManufacturer",
    "site": "LocationSite",
}


def check_decomposition(
    parsed_files: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """A denormalized sheet splits into one file per kind, referents first.

    Asserts (a) every kind the sheet conflates appears, each produced by
    exactly one NN-prefixed file (the sheet was split, not dumped into a
    single kind); (b) the repeated parent values were deduped (no duplicate
    HFID ``name`` within a referent kind); (c) referent kinds load before
    the referring kind (lower-or-equal NN prefix), so ``object load`` sees
    each reference target before the row that points at it.
    """
    if not parsed_files:
        return False, "No YAML files in output directory"

    # Map each kind to the NN prefix of the file(s) producing it.
    kind_to_num: dict[str, int] = {}
    kind_to_files: dict[str, set[Path]] = {}
    unnumbered: set[str] = set()
    for file_path, docs in parsed_files.items():
        m = _NN_PREFIX_RE.match(file_path.name)
        num = int(m.group(1)) if m else None
        for doc in docs:
            spec = doc.get("spec") or {}
            kind = spec.get("kind")
            if not isinstance(kind, str):
                continue
            kind_to_files.setdefault(kind, set()).add(file_path)
            if num is None:
                unnumbered.add(file_path.name)
            elif kind not in kind_to_num or num < kind_to_num[kind]:
                kind_to_num[kind] = num

    # (a) The sheet was split across every conflated kind, one file each.
    missing = sorted(FIXTURE_DECOMP_EXPECTED_KINDS - set(kind_to_files))
    if missing:
        return False, (
            f"Denormalized sheet not fully split — no rows for: {', '.join(missing)}"
        )
    if unnumbered:
        return False, (
            f"Emitted files lack an NN_ load-order prefix: {', '.join(sorted(unnumbered)[:5])}"
        )
    multi = [
        f"{k} in {len(fs)} files ({', '.join(sorted(f.name for f in fs))})"
        for k, fs in kind_to_files.items()
        if k in FIXTURE_DECOMP_EXPECTED_KINDS and len(fs) > 1
    ]
    if multi:
        return False, "Kind split across multiple files: " + "; ".join(multi[:4])

    # (b) Repeated parent values were deduped within each referent kind.
    dup_issues: list[str] = []
    for target_kind in sorted(set(FIXTURE_DECOMP_REFERENCES.values())):
        names: list[str] = []
        for _fp, kind, row in _walk_data_rows(parsed_files):
            if kind != target_kind:
                continue
            nm = _attr_value(row.get("name"))
            if isinstance(nm, str):
                names.append(nm)
        dups = sorted({n for n in names if names.count(n) > 1})
        if dups:
            dup_issues.append(f"{target_kind}: duplicate rows for {', '.join(dups)}")
    if dup_issues:
        return False, "Repeated parent rows not deduped: " + "; ".join(dup_issues[:4])

    # (c) Referent kinds load before the referring kind.
    order_issues: list[str] = []
    for rel_key, target_kind in FIXTURE_DECOMP_REFERENCES.items():
        target_num = kind_to_num.get(target_kind)
        if target_num is None:
            continue
        for file_path, _kind, row in _walk_data_rows(parsed_files):
            if rel_key not in row:
                continue
            m = _NN_PREFIX_RE.match(file_path.name)
            if m is None:
                continue
            if target_num > int(m.group(1)):
                order_issues.append(
                    f"{target_kind} (file {target_num:02d}) loads after a row "
                    f"referencing it via {rel_key!r} in {file_path.name}"
                )
                break
    if order_issues:
        return False, "Load order inverted: " + "; ".join(order_issues[:4])

    return True, (
        f"Denormalized sheet split into {len(kind_to_files)} kinds; referents "
        f"deduped and loaded before referrers"
    )


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------


CHECKS: dict[str, Any] = {
    "envelope": check_envelope,
    "load-order-numbering": check_load_order_numbering,
    "dropdown-names": check_dropdown_names,
    "hfid-reference-shape": check_hfid_reference_shape,
    "component-children-shape": check_component_children_shape,
    "range-expansion": check_range_expansion,
    "no-schema-mutation": check_no_schema_mutation,
    "value-coercion": check_value_coercion,
    "empty-and-null": check_empty_and_null,
    "csv-dialect": check_csv_dialect,
    "pre-flight-closure": check_pre_flight_closure,
    "provenance-comment": check_provenance_comment,
    "column-to-attribute": check_column_to_attribute,
    "merge-same-kind": check_merge_same_kind,
    "lineage-stamping": check_lineage_stamping,
    "fail-closed": check_fail_closed,
    "folder-coverage": check_folder_coverage,
    "decomposition": check_decomposition,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(check_names: list[str], output_dir: Path) -> dict:
    """Run named checks against the emitted output directory.

    Parameters
    ----------
    check_names:
        List of assertion names from the ``CHECKS`` registry.
    output_dir:
        Path to the directory holding the model's emitted YAML files.

    Returns
    -------
    dict with keys:
        - ``score`` (float 0.0-1.0)
        - ``details`` (str summary)
        - ``checks`` (list of ``{"name", "passed", "message"}``)
    """
    parsed = load_output_dir(output_dir)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            ok, msg = fn(parsed, output_dir=output_dir)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"

        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    if failed:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}
