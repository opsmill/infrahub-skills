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
