"""Shared grader library for infrahub-converting-netbox-device-types evals.

The NetBox conversion skill emits a *directory* of Infrahub object files
(``01_manufacturers.yml``, ``02_device_types.yml``,
``03_device_templates.yml``) plus a Markdown coverage report. The checks
here walk that directory and assert the shape defined by the rules in
``skills/infrahub-converting-netbox-device-types/rules/``.

Every check is deterministic: it parses the emitted YAML and Markdown and
returns a hard pass/fail. No LLM grading, no network.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(["envelope", "template-kind"], Path("./output_dir"))
    print(result)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    raise SystemExit("PyYAML is required: pip install pyyaml")


#: NetBox component lists a device-type file may declare.
NETBOX_COMPONENT_LISTS = (
    "console-ports",
    "console-server-ports",
    "power-ports",
    "power-outlets",
    "interfaces",
    "front-ports",
    "rear-ports",
    "module-bays",
    "device-bays",
    "inventory-items",
)

#: Model data that belongs on the device type, never on the template.
MODEL_ONLY_ATTRIBUTES = ("height", "u_height", "part_number", "weight", "full_depth")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _docs_from_file(text: str) -> list[dict]:
    """Parse every YAML document in one file, keeping only mappings."""
    docs: list[dict] = []
    try:
        for doc in yaml.safe_load_all(text):
            if isinstance(doc, dict):
                docs.append(doc)
    except yaml.YAMLError:
        return []
    return docs


def load_output_dir(path: Path) -> dict[Path, list[dict]]:
    """Parse every YAML file under ``path`` into documents.

    Args:
        path: Directory the model was asked to write into.

    Returns:
        Mapping of file path to the mapping documents it contains, sorted
        by filename so load order is observable.
    """
    if not path.is_dir():
        return {}
    parsed: dict[Path, list[dict]] = {}
    for file in sorted(path.rglob("*")):
        if file.suffix.lower() not in (".yml", ".yaml") or not file.is_file():
            continue
        try:
            parsed[file] = _docs_from_file(file.read_text(encoding="utf-8"))
        except OSError:
            parsed[file] = []
    return parsed


def _object_docs(parsed: dict[Path, list[dict]]) -> list[dict]:
    """Return every parsed document that looks like an Infrahub object file."""
    return [doc for docs in parsed.values() for doc in docs if "spec" in doc]


def _docs_of_kind(parsed: dict[Path, list[dict]], prefix: str) -> list[dict]:
    """Return object documents whose ``spec.kind`` starts with ``prefix``."""
    found = []
    for doc in _object_docs(parsed):
        spec = doc.get("spec")
        if isinstance(spec, dict) and str(spec.get("kind", "")).startswith(prefix):
            found.append(doc)
    return found


def _rows(doc: dict) -> list[dict]:
    """Return the ``spec.data`` rows of one object document."""
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        return []
    data = spec.get("data")
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _template_rows(parsed: dict[Path, list[dict]]) -> list[dict]:
    """Return every row of every ``Template*`` object document."""
    return [row for doc in _docs_of_kind(parsed, "Template") for row in _rows(doc)]


def _is_component_block(value: Any) -> bool:
    """True for a ``{kind, data}`` component block."""
    return isinstance(value, dict) and "data" in value


def component_blocks(row: dict) -> list[tuple[str, Any]]:
    """Return ``(relationship, block)`` pairs for one template row.

    A relationship carries either a single ``{kind, data: [...]}`` mapping or,
    when two NetBox lists share it, a list of ``{kind, data: {...}}`` items.
    Both are valid; a bare list of children is not, and is deliberately left
    out so the wrapper check still fails it.
    """
    pairs: list[tuple[str, Any]] = []
    for key, value in row.items():
        if _is_component_block(value):
            pairs.append((key, value))
        elif isinstance(value, list) and value and all(_is_component_block(v) for v in value):
            pairs.extend((key, block) for block in value)
    return pairs


def block_children(block: dict) -> list[dict]:
    """Return the children a component block carries, in either shape.

    The mapping form holds a list under ``data``; a list-form item holds one
    child mapping. Iterating ``data`` blindly would walk a child's *keys*
    under the list form and silently report zero children.
    """
    data = block.get("data")
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [child for child in data if isinstance(child, dict)]
    return []


def component_children(row: dict) -> list[tuple[str, dict]]:
    """Return ``(relationship, child)`` pairs across every component block."""
    return [
        (relationship, child)
        for relationship, block in component_blocks(row)
        for child in block_children(block)
    ]


def _read_text_files(output_dir: Path, suffixes: tuple[str, ...]) -> str:
    """Return the concatenated text of every matching file in the output."""
    if not output_dir.is_dir():
        return ""
    chunks = []
    for file in sorted(output_dir.rglob("*")):
        if not file.is_file() or file.suffix.lower() not in suffixes:
            continue
        try:
            chunks.append(file.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(chunks)


def _report_text(output_dir: Path) -> str:
    """Return the concatenated text of every Markdown file in the output."""
    return _read_text_files(output_dir, (".md",))


def _read_all_text(output_dir: Path) -> str:
    """Return the concatenated text of every text-ish file in the output."""
    return _read_text_files(output_dir, (".md", ".txt", ".yml", ".yaml"))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_envelope(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Every emitted document carries a well-formed Infrahub Object envelope."""
    docs = _object_docs(parsed)
    if not docs:
        return False, "No Infrahub object documents found in the output"
    for doc in docs:
        if doc.get("apiVersion") != "infrahub.app/v1":
            return False, f"Document has apiVersion {doc.get('apiVersion')!r}"
        if doc.get("kind") != "Object":
            return False, f"Document has kind {doc.get('kind')!r}, expected 'Object'"
        spec = doc.get("spec")
        if not isinstance(spec, dict) or not spec.get("kind"):
            return False, "Document is missing spec.kind"
        if not isinstance(spec.get("data"), list):
            return False, f"spec.data for {spec.get('kind')} is not a list"
    return True, f"All {len(docs)} object documents carry a valid envelope"


def check_template_kind(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Templates are authored under a ``Template<Kind>``, not the base node kind."""
    templates = _docs_of_kind(parsed, "Template")
    if not templates:
        kinds = sorted(
            {str(doc["spec"].get("kind")) for doc in _object_docs(parsed) if "spec" in doc}
        )
        return False, f"No Template* object document found; kinds present: {kinds}"
    for doc in templates:
        for row in _rows(doc):
            if not row.get("template_name"):
                return False, f"A {doc['spec']['kind']} row is missing template_name"
    return True, f"{len(templates)} Template* document(s), every row named"


def check_no_model_data_on_template(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Physical model data lives on the device type, not on the template."""
    rows = _template_rows(parsed)
    if not rows:
        return False, "No Template* rows found"
    for row in rows:
        leaked = [attr for attr in MODEL_ONLY_ATTRIBUTES if attr in row]
        if leaked:
            return False, (
                f"Template {row.get('template_name')!r} carries model data "
                f"{leaked}; that belongs on the device type object"
            )
    return True, f"No model data on any of {len(rows)} template rows"


def check_component_kind_wrapper(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Component children nest under a ``kind`` + ``data`` wrapper."""
    rows = _template_rows(parsed)
    if not rows:
        return False, "No Template* rows found"
    wrapped = 0
    for row in rows:
        for key, value in row.items():
            if not isinstance(value, (dict, list)):
                continue
            if isinstance(value, list):
                # A list is valid only when every item is a {kind, data}
                # block — the shape two NetBox lists sharing one
                # relationship produce. A bare list of children is not.
                if not value or not all(_is_component_block(item) for item in value):
                    return False, (
                        f"Component relationship {key!r} on "
                        f"{row.get('template_name')!r} is a bare list; expected a "
                        "mapping with 'kind' and 'data', or a list of such blocks"
                    )
            elif "data" not in value:
                return False, f"Component relationship {key!r} has no 'data' key"
            blocks = [value] if isinstance(value, dict) else value
            for block in blocks:
                if not str(block.get("kind", "")).startswith("Template"):
                    return False, (
                        f"Component relationship {key!r} has kind "
                        f"{block.get('kind')!r}; expected a Template* kind"
                    )
                wrapped += 1
    if wrapped == 0:
        return False, "No component children were emitted under any template"
    return True, f"{wrapped} component relationship(s) correctly wrapped"


def check_component_template_names_namespaced(
    parsed: dict[Path, list[dict]], **_: Any
) -> tuple[bool, str]:
    """Component template names are unique and namespaced by their parent."""
    seen: dict[str, str] = {}
    checked = 0
    for row in _template_rows(parsed):
        parent = str(row.get("template_name", ""))
        for relationship, child in component_children(row):
            name = child.get("template_name")
            if not name:
                return False, f"A {relationship!r} child of {parent!r} has no template_name"
            if parent and parent not in str(name):
                return False, (
                    f"Component template {name!r} is not namespaced by its "
                    f"parent {parent!r}; names collide across device types"
                )
            if name in seen:
                return False, f"Duplicate component template_name {name!r}"
            seen[str(name)] = parent
            checked += 1
    if checked == 0:
        return False, "No component templates were emitted"
    return True, f"{checked} component template name(s) unique and parent-namespaced"


def check_device_type_object(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """A device type object carries the model data and names its manufacturer."""
    candidates = [
        doc
        for doc in _object_docs(parsed)
        if "devicetype" in str(doc["spec"].get("kind", "")).lower()
    ]
    if not candidates:
        return False, "No device type object document found"
    for doc in candidates:
        for row in _rows(doc):
            if not row.get("manufacturer"):
                return False, f"Device type row {row!r} does not name a manufacturer"
            if not any(attr in row for attr in ("height", "part_number", "weight")):
                return False, (
                    f"Device type row {row.get('name')!r} carries no model data "
                    "(height / part_number / weight)"
                )
    return True, f"{len(candidates)} device type document(s) carry model data"


def check_module_type_objects(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Module type objects carry their model data and name a manufacturer.

    A NetBox module type is mostly its component list, and most schemas have
    no component relationship on the module type — so this asserts the parts
    that *can* land: the model identity and the manufacturer link.
    """
    # Identify by the emitted filename, not the kind: a concrete module type
    # need not have "module" in its name (DeviceLinecardType is the worked
    # example in schema-library), so a kind-substring test misses it.
    rows = [
        row
        for path, docs in parsed.items()
        if "module_type" in path.name and "template" not in path.name
        for doc in docs
        if "spec" in doc
        for row in _rows(doc)
    ]
    if not rows:
        names = sorted(p.name for p in parsed)
        return False, (
            "No module type object file found (expected one named like "
            f"04_module_types.yml); files present: {names}"
        )

    seen: set[str] = set()
    for row in rows:
        name = row.get("name")
        if not name:
            return False, f"Module type row {row!r} has no name"
        if name in seen:
            return False, f"Duplicate module type name {name!r}"
        seen.add(str(name))
        if not row.get("manufacturer"):
            return False, f"Module type {name!r} does not name a manufacturer"
    return True, f"{len(rows)} module type object(s) named and attributed"


def check_load_order_numbering(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Emitted files are numbered so manufacturers load before templates."""
    numbered = [p for p in parsed if re.match(r"^\d+[-_]", p.name)]
    if len(numbered) < 3:
        return False, (
            "Expected at least 3 numbered object files "
            f"(manufacturers, device types, templates); found {len(numbered)}: "
            f"{sorted(p.name for p in parsed)}"
        )

    def rank(path: Path) -> int:
        match = re.match(r"^(\d+)", path.name)
        return int(match.group(1)) if match else 0

    positions: dict[str, int] = {}
    for path in numbered:
        for doc in parsed[path]:
            spec = doc.get("spec")
            if isinstance(spec, dict) and spec.get("kind"):
                positions.setdefault(str(spec["kind"]), rank(path))

    manufacturer = min(
        (pos for kind, pos in positions.items() if "manufacturer" in kind.lower()),
        default=None,
    )
    device_type = min(
        (pos for kind, pos in positions.items() if "devicetype" in kind.lower()),
        default=None,
    )
    template = min(
        (pos for kind, pos in positions.items() if kind.startswith("Template")),
        default=None,
    )
    if manufacturer is None or device_type is None or template is None:
        return False, f"Missing one of manufacturer/device type/template; saw {positions}"
    if not manufacturer < device_type < template:
        return False, (
            "Load order is wrong: manufacturers must precede device types, which "
            f"must precede templates (got {manufacturer}, {device_type}, {template})"
        )
    return True, "Files numbered in dependency order"


def check_coverage_report(
    parsed: dict[Path, list[dict]], output_dir: Path | None = None, **_: Any
) -> tuple[bool, str]:
    """A coverage report names the component lists that did not convert."""
    text = _report_text(output_dir or Path("."))
    if not text.strip():
        return False, "No Markdown coverage report found in the output directory"

    converted = set()
    for row in _template_rows(parsed):
        converted.update(relationship for relationship, _ in component_blocks(row))

    mentioned = [name for name in NETBOX_COMPONENT_LISTS if name in text]
    if not mentioned:
        return False, (
            "The report names none of the NetBox component lists; it cannot be "
            "telling the reader what was skipped"
        )
    if not converted and "interfaces" not in text:
        return False, "The report does not account for the interfaces list"
    return True, f"Coverage report names {len(mentioned)} component list(s)"


def check_shared_relationship_blocks(parsed: dict[Path, list[dict]], **_: Any) -> tuple[bool, str]:
    """Component lists sharing one relationship keep every child, in a loadable shape.

    Two NetBox lists can legitimately land on one Infrahub relationship when
    their peer kinds share a generic. Two things can go wrong, and both are
    invisible in the coverage report:

    1. Assigning rather than accumulating makes the second mapping erase the
       first while the report still claims both converted.
    2. Accumulating into the *wrong* shape. The object loader treats a list
       payload as ``MANY_OBJ_LIST_DICT`` and hands each item's ``data``
       straight to its single-object path, so nesting a list of children
       inside a list item fails the load with ``AttributeError: 'list' object
       has no attribute 'items'``. Each item must carry exactly one child.

    The second is why this check inspects the shape of ``data`` rather than
    only counting blocks: the grouped form is self-consistent and looks
    plausible right up to the point a server rejects it.
    """
    rows = _template_rows(parsed)
    if not rows:
        return False, "No Template* rows found"

    shared = 0
    for row in rows:
        by_relationship: dict[str, list[Any]] = {}
        for relationship, block in component_blocks(row):
            by_relationship.setdefault(relationship, []).append(block)
        for relationship, blocks in by_relationship.items():
            if len(blocks) == 1:
                continue
            shared += 1
            for block in blocks:
                if isinstance(block.get("data"), list):
                    return False, (
                        f"Relationship {relationship!r} on "
                        f"{row.get('template_name')!r} nests a list of children "
                        f"under a list item's 'data' ({block.get('kind')!r}). The "
                        "loader passes each item's 'data' to its single-object "
                        "path, so this fails to load — emit one child per item."
                    )
                if not block_children(block):
                    return False, (
                        f"Relationship {relationship!r} on "
                        f"{row.get('template_name')!r} has an empty "
                        f"{block.get('kind')!r} block"
                    )
            kinds = {str(block.get("kind")) for block in blocks}
            if len(kinds) < 2:
                return False, (
                    f"Relationship {relationship!r} on {row.get('template_name')!r} "
                    f"carries {len(blocks)} items of one kind ({kinds}); a shared "
                    "relationship should show more than one peer kind"
                )
    if shared == 0:
        return False, (
            "No relationship carries more than one component block, so nothing "
            "exercised the shared-relationship path"
        )
    return True, f"{shared} shared relationship(s) kept every child in the loadable shape"


def check_fallback_precedence(
    parsed: dict[Path, list[dict]], output_dir: Path | None = None, **_: Any
) -> tuple[bool, str]:
    """A declared fallback filled a gap, and shadowed values are reported.

    Deliberately does not judge *which* source won for a given record: from
    the output alone, "comments won because description was absent" and
    "comments won although description was set" look identical. The former
    is correct behaviour and common in the real library, so a check that
    flags datasheet URLs produces false failures. Precedence for a known
    input is asserted by the task grader that owns the fixture.
    """
    device_types = [
        row
        for doc in _object_docs(parsed)
        if "devicetype" in str(doc["spec"].get("kind", "")).lower()
        for row in _rows(doc)
    ]
    if not device_types:
        return False, "No device type rows found"

    described = [
        child
        for row in _template_rows(parsed)
        for _, child in component_children(row)
        if child.get("description")
    ]
    if not described:
        return False, (
            "No component template carries a description; the fallback did not "
            "fill in where the primary source was absent"
        )

    text = _report_text(output_dir or Path("."))
    if not text.strip():
        return False, "No coverage report found, so shadowed values cannot be reported"
    if "hadow" not in text:
        return False, (
            "The report records no shadowed value even though competing fields "
            "were present; a discarded value went unreported"
        )
    return True, f"Fallback used across {len(device_types)} device type(s), shadowing reported"


def check_generate_template_prerequisite(
    _parsed: dict[Path, list[dict]], output_dir: Path | None = None, **_: Any
) -> tuple[bool, str]:
    """The schema prerequisite ``generate_template: true`` is surfaced."""
    directory = output_dir or Path(".")
    haystack = _read_all_text(directory)
    if "generate_template" not in haystack:
        return False, (
            "Nothing in the output mentions generate_template; the Template* "
            "kinds do not exist until it is enabled on the node"
        )
    if not re.search(r"generate_template\s*:\s*true", haystack):
        return False, "generate_template is mentioned but not shown set to true"
    return True, "The generate_template prerequisite is surfaced"


CHECKS: dict[str, Callable[..., tuple[bool, str]]] = {
    "envelope": check_envelope,
    "template-kind": check_template_kind,
    "no-model-data-on-template": check_no_model_data_on_template,
    "component-kind-wrapper": check_component_kind_wrapper,
    "component-names-namespaced": check_component_template_names_namespaced,
    "device-type-object": check_device_type_object,
    "module-type-object": check_module_type_objects,
    "load-order-numbering": check_load_order_numbering,
    "coverage-report": check_coverage_report,
    "shared-relationship-blocks": check_shared_relationship_blocks,
    "fallback-precedence": check_fallback_precedence,
    "generate-template-prerequisite": check_generate_template_prerequisite,
}


def run_checks(check_names: list[str], output_dir: Path) -> dict:
    """Run named checks against the emitted output directory.

    Args:
        check_names: Assertion names from the ``CHECKS`` registry.
        output_dir: Directory holding the model's emitted files.

    Returns:
        A dict with ``score`` (float 0.0-1.0), ``details`` (str), and
        ``checks`` (list of ``{"name", "passed", "message"}``).
    """
    parsed = load_output_dir(output_dir)

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(parsed, output_dir=output_dir)
        except Exception as exc:  # pragma: no cover - defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [entry["name"] for entry in entries if not entry["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed
        else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}
