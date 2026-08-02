#!/usr/bin/env python3
"""Convert NetBox device and module types into Infrahub object YAML.

Reads one or more NetBox ``devicetype-library`` YAML files (the format
published at https://github.com/netbox-community/devicetype-library and
browsable via the NetBox Data Exchange) and emits Infrahub object files:

1. Manufacturer objects
2. Device type objects (which carry the physical model data)
3. Object templates (``Template<Kind>``) plus their nested component
   templates
4. Module type objects
5. Module templates, when the profile configures them

Both NetBox input families are accepted in a single pass. Device types
and module types are told apart by the presence of ``slug``, which every
device type carries and no module type does, so a mixed tree converts
without being split up first. Files with no content are not written.

The Infrahub side of the conversion is never hardcoded. Every kind,
attribute name, and relationship name comes from a *mapping profile* --
a YAML file describing the target schema. A default profile for the
OpsMill schema-library DCIM schema ships in ``mappings/schema-library.yml``.

Anything in the NetBox input the profile does not map is skipped and
recorded in a coverage report, so the data loss is visible rather than
silent.

Usage
-----
::

    python netbox_to_infrahub_templates.py device-types/Cisco/ \\
        --mapping mappings/schema-library.yml \\
        --output-dir ./generated

    python netbox_to_infrahub_templates.py c9300-48p.yaml \\
        --mapping mappings/schema-library.yml \\
        --output-dir ./generated \\
        --report -

Exit codes
----------
0
    Conversion completed (possibly with skipped components).
1
    Bad mapping profile, unreadable input, or malformed NetBox file.
2
    No input files matched.
"""

from __future__ import annotations

import argparse
import glob
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# NetBox format constants
# --------------------------------------------------------------------------

#: Every component list a NetBox device-type file may declare.
NETBOX_COMPONENT_LISTS: tuple[str, ...] = (
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

#: Every top-level scalar field a NetBox device-type file may declare.
NETBOX_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "manufacturer",
    "model",
    "slug",
    "part_number",
    "u_height",
    "is_full_depth",
    "airflow",
    "front_image",
    "rear_image",
    "subdevice_role",
    "comments",
    "description",
    "is_powered",
    "weight",
    "weight_unit",
)

#: Every top-level scalar field a NetBox module-type file may declare.
#: Module types carry no ``slug`` — that absence is how the two input
#: families are told apart.
NETBOX_MODULE_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "manufacturer",
    "model",
    "part_number",
    "comments",
    "description",
    "weight",
    "weight_unit",
    "airflow",
    "profile",
    "attribute_data",
)

#: Fields required by the NetBox device-type JSON schema.
NETBOX_REQUIRED_FIELDS: tuple[str, ...] = ("manufacturer", "model", "slug")

#: Fields required of a NetBox module-type.
NETBOX_MODULE_REQUIRED_FIELDS: tuple[str, ...] = ("manufacturer", "model")

DEVICE_TYPES = "device-types"
MODULE_TYPES = "module-types"

#: Token NetBox substitutes with the bay position when a module is
#: installed. It appears in 93.9% of published module-type component names
#: and cannot be resolved at template time, because a template is not bound
#: to a bay.
MODULE_POSITION_TOKEN = "{module}"

#: Conversion factors from each NetBox weight unit to kilograms.
WEIGHT_TO_KG: dict[str, float] = {
    "kg": 1.0,
    "g": 0.001,
    "lb": 0.45359237,
    "oz": 0.028349523125,
}

SUPPORTED_TRANSFORMS: tuple[str, ...] = ("text", "number", "boolean", "weight_kg")

#: Emitted in dependency order. Module types depend only on manufacturers,
#: so they sit after the device files rather than renumbering them.
OUTPUT_FILENAMES: dict[str, str] = {
    "manufacturer": "01_manufacturers.yml",
    "device_type": "02_device_types.yml",
    "template": "03_device_templates.yml",
    "module_type": "04_module_types.yml",
    "module_template": "05_module_templates.yml",
}


class ConversionError(Exception):
    """Raised when input or configuration cannot be processed."""


# --------------------------------------------------------------------------
# Mapping profile
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldMapping:
    """One NetBox field mapped onto one Infrahub attribute.

    Args:
        source: Preferred NetBox field name (top level or component level).
        target: Infrahub attribute name on the destination kind.
        transform: Value transform to apply; one of ``SUPPORTED_TRANSFORMS``.
        fallbacks: Further NetBox fields to try, in order, when the
            preferred source is absent or empty.
    """

    source: str
    target: str
    transform: str = "text"
    fallbacks: tuple[str, ...] = ()

    @property
    def sources(self) -> tuple[str, ...]:
        """Every NetBox field this mapping may read, in priority order."""
        return (self.source, *self.fallbacks)


@dataclass(frozen=True)
class DerivedField:
    """An Infrahub attribute set from a condition on the NetBox entry.

    Args:
        target: Infrahub attribute name to set.
        when: NetBox field/value pairs that must all match.
        value: Value written to ``target`` when the condition holds.
    """

    target: str
    when: dict[str, Any]
    value: Any


@dataclass(frozen=True)
class ComponentMapping:
    """A NetBox component list mapped onto an Infrahub component template.

    Args:
        netbox_list: NetBox component list name, e.g. ``interfaces``.
        kind: Concrete Infrahub template kind, e.g. ``TemplateInterfacePhysical``.
        relationship: Component relationship name on the parent template.
        template_name: Format string for the child ``template_name``.
        fields: Field mappings applied to each component entry.
        derived: Conditional attributes applied to each component entry.
        defaults: Attributes written on every component entry.
    """

    netbox_list: str
    kind: str
    relationship: str
    template_name: str
    fields: tuple[FieldMapping, ...]
    derived: tuple[DerivedField, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleTarget:
    """How NetBox module types map onto Infrahub kinds.

    Structurally the same split as device types: a type object carrying the
    model facts, and optionally a template carrying the components. Most
    schemas can only do the first — the stock schema-library module type
    has no component relationships — so the template half is optional.

    Args:
        kind: Concrete Infrahub kind for the module type object.
        manufacturer_relationship: Relationship to the manufacturer.
        fields: NetBox field to Infrahub attribute mappings.
        defaults: Attributes written on every module type.
        key_format: Format string identifying a module type; NetBox module
            types carry no slug, and ``model`` is unique library-wide.
        template_kind: Optional ``Template<Kind>`` for installed modules.
        template_name_format: Format string for that template's name.
        template_type_relationship: Relationship from module to module type.
        template_defaults: Attributes written on every module template.
        components: Component lists mapped onto the module template.
        position_placeholder: Value substituted for ``{module}`` in
            component names; ``None`` keeps the token literal.
    """

    kind: str
    manufacturer_relationship: str
    fields: tuple[FieldMapping, ...]
    defaults: dict[str, Any]
    key_format: str
    template_kind: str | None = None
    template_name_format: str | None = None
    template_type_relationship: str | None = None
    template_defaults: dict[str, Any] = field(default_factory=dict)
    components: tuple[ComponentMapping, ...] = ()
    position_placeholder: str | None = None

    @property
    def emits_templates(self) -> bool:
        """True when the profile configures a module template."""
        return bool(self.template_kind)

    @property
    def mapped_lists(self) -> set[str]:
        """NetBox component lists this target knows how to convert."""
        return {component.netbox_list for component in self.components}


@dataclass(frozen=True)
class Profile:
    """A validated mapping profile describing the target Infrahub schema."""

    name: str
    manufacturer_kind: str
    manufacturer_name_field: str
    device_type_kind: str
    device_type_manufacturer_rel: str
    device_type_fields: tuple[FieldMapping, ...]
    device_type_defaults: dict[str, Any]
    template_kind: str
    template_name_format: str
    template_device_type_rel: str
    template_defaults: dict[str, Any]
    components: tuple[ComponentMapping, ...]
    modules: ModuleTarget | None = None

    @property
    def mapped_lists(self) -> set[str]:
        """NetBox component lists this profile knows how to convert."""
        return {component.netbox_list for component in self.components}


def _require_mapping(raw: Any, path: str) -> dict[str, Any]:
    """Return ``raw`` as a dict or raise with the offending profile path."""
    if not isinstance(raw, dict):
        raise ConversionError(f"Mapping profile: '{path}' must be a mapping")
    return raw


def _parse_fields(raw: Any, path: str) -> tuple[FieldMapping, ...]:
    """Parse a ``fields:`` block into ``FieldMapping`` entries.

    Accepts either the short form (``model: name``) or the long form
    (``u_height: {target: height, transform: number}``). The long form may
    also declare ``fallback``, a field name or list of field names tried in
    order when the preferred source is absent or empty.
    """
    mappings: list[FieldMapping] = []
    for source, spec in _require_mapping(raw or {}, path).items():
        if isinstance(spec, str):
            mappings.append(FieldMapping(source=source, target=spec))
            continue
        spec_map = _require_mapping(spec, f"{path}.{source}")
        target = spec_map.get("target")
        if not isinstance(target, str) or not target:
            raise ConversionError(f"Mapping profile: '{path}.{source}' needs a 'target'")
        transform = spec_map.get("transform", "text")
        if transform not in SUPPORTED_TRANSFORMS:
            raise ConversionError(
                f"Mapping profile: '{path}.{source}.transform' must be one of "
                f"{', '.join(SUPPORTED_TRANSFORMS)}"
            )
        mappings.append(
            FieldMapping(
                source=source,
                target=target,
                transform=transform,
                fallbacks=_parse_fallbacks(spec_map.get("fallback"), source, f"{path}.{source}"),
            )
        )
    _reject_conflicting_targets(mappings, path)
    return tuple(mappings)


def _parse_fallbacks(raw: Any, source: str, path: str) -> tuple[str, ...]:
    """Parse a ``fallback`` declaration into an ordered tuple of field names."""
    if raw is None:
        return ()
    names = [raw] if isinstance(raw, str) else raw
    if not isinstance(names, list) or not all(isinstance(name, str) and name for name in names):
        raise ConversionError(
            f"Mapping profile: '{path}.fallback' must be a field name or a list of field names"
        )
    if source in names:
        raise ConversionError(f"Mapping profile: '{path}.fallback' lists its own source {source!r}")
    if len(set(names)) != len(names):
        raise ConversionError(f"Mapping profile: '{path}.fallback' repeats a field name")
    return tuple(names)


def _reject_conflicting_targets(mappings: list[FieldMapping], path: str) -> None:
    """Reject two mappings writing the same target without a declared order.

    Two NetBox fields competing for one Infrahub attribute is a real
    situation (``description`` vs ``comments``), but silently letting the
    last one win hides the loss. Declaring one as the other's ``fallback``
    makes the precedence explicit and lets the shadowed value be reported.
    """
    seen: dict[str, str] = {}
    for mapping in mappings:
        if mapping.target in seen:
            raise ConversionError(
                f"Mapping profile: '{path}' maps both {seen[mapping.target]!r} and "
                f"{mapping.source!r} onto {mapping.target!r}; declare one as the "
                "other's 'fallback' so the precedence is explicit"
            )
        seen[mapping.target] = mapping.source


def _parse_derived(raw: Any, path: str) -> tuple[DerivedField, ...]:
    """Parse a ``derived:`` block into ``DerivedField`` entries."""
    derived: list[DerivedField] = []
    for target, spec in _require_mapping(raw or {}, path).items():
        spec_map = _require_mapping(spec, f"{path}.{target}")
        when = _require_mapping(spec_map.get("when", {}), f"{path}.{target}.when")
        if not when:
            raise ConversionError(f"Mapping profile: '{path}.{target}.when' cannot be empty")
        if "value" not in spec_map:
            raise ConversionError(f"Mapping profile: '{path}.{target}' needs a 'value'")
        derived.append(DerivedField(target=target, when=dict(when), value=spec_map["value"]))
    return tuple(derived)


def _parse_components(raw: Any, path: str = "components") -> tuple[ComponentMapping, ...]:
    """Parse a ``components:`` block of a mapping profile."""
    components: list[ComponentMapping] = []
    for netbox_list, spec in _require_mapping(raw or {}, path).items():
        entry_path = f"{path}.{netbox_list}"
        if netbox_list not in NETBOX_COMPONENT_LISTS:
            raise ConversionError(
                f"Mapping profile: '{entry_path}' is not a NetBox component list "
                f"({', '.join(NETBOX_COMPONENT_LISTS)})"
            )
        spec_map = _require_mapping(spec, entry_path)
        for required in ("kind", "relationship", "template_name"):
            if not spec_map.get(required):
                raise ConversionError(f"Mapping profile: '{entry_path}' needs '{required}'")
        components.append(
            ComponentMapping(
                netbox_list=netbox_list,
                kind=spec_map["kind"],
                relationship=spec_map["relationship"],
                template_name=spec_map["template_name"],
                fields=_parse_fields(spec_map.get("fields"), f"{entry_path}.fields"),
                derived=_parse_derived(spec_map.get("derived"), f"{entry_path}.derived"),
                defaults=dict(
                    _require_mapping(spec_map.get("defaults", {}), f"{entry_path}.defaults")
                ),
            )
        )
    return tuple(components)


def _parse_module_target(raw: Any) -> ModuleTarget | None:
    """Parse the optional ``module_type`` section of a mapping profile."""
    if raw is None:
        return None
    section = _require_mapping(raw, "module_type")
    for key in ("kind", "manufacturer_relationship"):
        if not section.get(key):
            raise ConversionError(f"Mapping profile: 'module_type' missing required key '{key}'")

    template = _require_mapping(section.get("template", {}) or {}, "module_type.template")
    if template and not template.get("kind"):
        raise ConversionError("Mapping profile: 'module_type.template' needs a 'kind'")
    if template and not template.get("template_name"):
        raise ConversionError("Mapping profile: 'module_type.template' needs a 'template_name'")

    components = _parse_components(section.get("components"), path="module_type.components")
    if components and not template:
        raise ConversionError(
            "Mapping profile: 'module_type.components' needs 'module_type.template' — "
            "components hang off a module template, and most schemas have no "
            "component relationship on the module type itself"
        )

    placeholder = section.get("position_placeholder")
    if placeholder is not None and not isinstance(placeholder, (str, int)):
        raise ConversionError(
            "Mapping profile: 'module_type.position_placeholder' must be a string or number"
        )

    return ModuleTarget(
        kind=section["kind"],
        manufacturer_relationship=section["manufacturer_relationship"],
        fields=_parse_fields(section.get("fields"), "module_type.fields"),
        defaults=dict(_require_mapping(section.get("defaults", {}), "module_type.defaults")),
        key_format=str(section.get("key", "{model}")),
        template_kind=template.get("kind"),
        template_name_format=template.get("template_name"),
        template_type_relationship=template.get("module_type_relationship"),
        template_defaults=dict(
            _require_mapping(template.get("defaults", {}), "module_type.template.defaults")
        ),
        components=components,
        position_placeholder=None if placeholder is None else str(placeholder),
    )


def load_profile(path: Path) -> Profile:
    """Load and validate a mapping profile from disk.

    Args:
        path: Path to the mapping profile YAML file.

    Returns:
        The validated profile.

    Raises:
        ConversionError: If the file is unreadable or structurally invalid.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConversionError(f"Cannot read mapping profile {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConversionError(f"Mapping profile {path} is not valid YAML: {exc}") from exc

    root = _require_mapping(raw, "<root>")
    manufacturer = _require_mapping(root.get("manufacturer"), "manufacturer")
    device_type = _require_mapping(root.get("device_type"), "device_type")
    template = _require_mapping(root.get("template"), "template")

    for section, key in (
        (manufacturer, "kind"),
        (manufacturer, "name_field"),
        (device_type, "kind"),
        (device_type, "manufacturer_relationship"),
        (template, "kind"),
        (template, "template_name"),
        (template, "device_type_relationship"),
    ):
        if not section.get(key):
            raise ConversionError(f"Mapping profile: missing required key '{key}'")

    return Profile(
        name=str(root.get("name", path.stem)),
        manufacturer_kind=manufacturer["kind"],
        manufacturer_name_field=manufacturer["name_field"],
        device_type_kind=device_type["kind"],
        device_type_manufacturer_rel=device_type["manufacturer_relationship"],
        device_type_fields=_parse_fields(device_type.get("fields"), "device_type.fields"),
        device_type_defaults=dict(
            _require_mapping(device_type.get("defaults", {}), "device_type.defaults")
        ),
        template_kind=template["kind"],
        template_name_format=template["template_name"],
        template_device_type_rel=template["device_type_relationship"],
        template_defaults=dict(_require_mapping(template.get("defaults", {}), "template.defaults")),
        components=_parse_components(root.get("components")),
        modules=_parse_module_target(root.get("module_type")),
    )


# --------------------------------------------------------------------------
# NetBox input
# --------------------------------------------------------------------------


def detect_input_kind(data: dict[str, Any]) -> str:
    """Tell a NetBox device-type file from a module-type file.

    ``slug`` is required of every device type and carried by no module
    type — across the 1,909 published module types, none declares one — so
    its presence is a reliable discriminator and lets a mixed tree be
    converted in one pass.

    Args:
        data: The parsed NetBox mapping.

    Returns:
        Either ``DEVICE_TYPES`` or ``MODULE_TYPES``.
    """
    return DEVICE_TYPES if data.get("slug") else MODULE_TYPES


@dataclass(frozen=True)
class DeviceType:
    """A parsed NetBox device-type or module-type definition.

    Args:
        source: Path the definition was read from.
        data: The raw parsed YAML mapping.
        input_kind: Which NetBox input family this came from.
    """

    source: Path
    data: dict[str, Any]
    input_kind: str = DEVICE_TYPES

    @property
    def is_module(self) -> bool:
        """True for a NetBox module type."""
        return self.input_kind == MODULE_TYPES

    @property
    def manufacturer(self) -> str:
        """The manufacturer name."""
        return str(self.data["manufacturer"])

    @property
    def model(self) -> str:
        """The device model name."""
        return str(self.data["model"])

    @property
    def slug(self) -> str:
        """The NetBox slug, unique across the library.

        Module types carry none, so the model — unique across all 1,909
        published module types — stands in as the identity.
        """
        return str(self.data.get("slug") or self.data["model"])

    def components(self, list_name: str) -> list[dict[str, Any]]:
        """Return the entries of one NetBox component list."""
        entries = self.data.get(list_name) or []
        if not isinstance(entries, list):
            raise ConversionError(f"{self.source}: '{list_name}' must be a list")
        return [entry for entry in entries if isinstance(entry, dict)]


def iter_input_files(paths: list[str]) -> list[Path]:
    """Expand CLI inputs into a sorted, de-duplicated list of YAML files.

    Directories are walked recursively; glob patterns are expanded. Files
    whose suffix is not ``.yaml``/``.yml`` are ignored when they arrive via
    a directory walk, and rejected when named explicitly.

    Args:
        paths: Raw file, directory, or glob arguments from the CLI.

    Returns:
        Sorted unique paths to candidate NetBox YAML files.

    Raises:
        ConversionError: If an explicit path does not exist.
    """
    found: set[Path] = set()
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_dir():
            for suffix in ("*.yaml", "*.yml"):
                found.update(p for p in candidate.rglob(suffix) if p.is_file())
        elif candidate.is_file():
            found.add(candidate)
        else:
            expanded = [Path(p) for p in glob.glob(raw, recursive=True)]
            matches = [p for p in expanded if p.is_file()]
            if not matches and not expanded:
                raise ConversionError(f"Input path does not exist: {raw}")
            found.update(matches)
    return sorted(found)


def parse_device_type(path: Path) -> DeviceType:
    """Parse one NetBox device-type YAML file.

    Args:
        path: Path to the device-type file.

    Returns:
        The parsed device type.

    Raises:
        ConversionError: If the file is unreadable, is not a mapping, or is
            missing a NetBox-required field.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConversionError(f"Cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConversionError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConversionError(f"{path}: expected a YAML mapping at the top level")

    input_kind = detect_input_kind(raw)
    required = (
        NETBOX_MODULE_REQUIRED_FIELDS if input_kind == MODULE_TYPES else NETBOX_REQUIRED_FIELDS
    )
    missing = [key for key in required if not raw.get(key)]
    if missing:
        label = "module-type" if input_kind == MODULE_TYPES else "device-type"
        hint = (
            " (no 'slug', so this was read as a module type)" if input_kind == MODULE_TYPES else ""
        )
        raise ConversionError(
            f"{path}: missing required NetBox {label} field(s): {', '.join(missing)}{hint}"
        )

    return DeviceType(source=path, data=raw, input_kind=input_kind)


# --------------------------------------------------------------------------
# Value transforms
# --------------------------------------------------------------------------


def _to_number(value: Any) -> tuple[Any, str | None]:
    """Coerce a NetBox numeric value, reporting non-integer inputs."""
    if isinstance(value, bool):
        return int(value), None
    if isinstance(value, int):
        return value, None
    if isinstance(value, float):
        if value.is_integer():
            return int(value), None
        return value, f"non-integer value {value} kept as float"
    try:
        return int(str(value)), None
    except ValueError:
        return value, f"value {value!r} is not numeric and was passed through unchanged"


def _to_kilograms(value: Any, unit: Any) -> tuple[Any, str | None]:
    """Convert a NetBox weight to kilograms, rounded to 3 decimal places."""
    unit_name = str(unit or "kg").lower()
    factor = WEIGHT_TO_KG.get(unit_name)
    if factor is None:
        return value, f"unknown weight_unit {unit_name!r}; value passed through unchanged"
    try:
        kilograms = round(float(value) * factor, 3)
    except (TypeError, ValueError):
        return value, f"weight {value!r} is not numeric and was passed through unchanged"
    if unit_name == "kg":
        return kilograms, None
    return kilograms, f"weight {value} {unit_name} converted to {kilograms} kg"


def apply_transform(
    mapping: FieldMapping, value: Any, source: dict[str, Any]
) -> tuple[Any, str | None]:
    """Apply a field mapping's transform to one NetBox value.

    Args:
        mapping: The field mapping being applied.
        value: The raw NetBox value.
        source: The NetBox entry the value came from, for unit lookups.

    Returns:
        A ``(value, note)`` pair; ``note`` is ``None`` when the value went
        through unchanged and non-``None`` when a coercion is worth reporting.
    """
    if mapping.transform == "number":
        return _to_number(value)
    if mapping.transform == "boolean":
        return bool(value), None
    if mapping.transform == "weight_kg":
        return _to_kilograms(value, source.get("weight_unit"))
    return value, None


def _is_present(value: Any) -> bool:
    """Return True when a NetBox value is worth mapping (not absent or blank)."""
    if value is None:
        return False
    return not (isinstance(value, str) and not value.strip())


def resolve_source(
    mapping: FieldMapping, entry: dict[str, Any]
) -> tuple[str | None, Any, list[str]]:
    """Pick the winning NetBox field for a mapping and note the shadowed ones.

    Args:
        mapping: The field mapping being applied.
        entry: The NetBox mapping to read from.

    Returns:
        A ``(source, value, shadowed)`` triple. ``source`` is ``None`` when
        no declared field carries a value. ``shadowed`` lists the other
        declared fields that *did* carry a value and were therefore
        discarded — those are a real loss and belong in the report.
    """
    winner: str | None = None
    value: Any = None
    shadowed: list[str] = []
    for name in mapping.sources:
        if not _is_present(entry.get(name)):
            continue
        if winner is None:
            winner, value = name, entry[name]
        else:
            shadowed.append(name)
    return winner, value, shadowed


def _format_name(template: str, values: dict[str, Any]) -> str:
    """Render a ``template_name`` format string, erroring on unknown fields."""
    try:
        return template.format(**values)
    except KeyError as exc:
        raise ConversionError(
            f"template_name {template!r} references unknown field {exc.args[0]!r}; "
            f"available: {', '.join(sorted(values))}"
        ) from exc


def _matches(entry: dict[str, Any], when: dict[str, Any]) -> bool:
    """Return True when every ``when`` field/value pair matches ``entry``."""
    return all(entry.get(key) == expected for key, expected in when.items())


def format_fields(template: str) -> set[str]:
    """Return the field names a ``template_name`` format string references.

    A field consumed by a template name is not lost data, so the coverage
    report must not report it as dropped.
    """
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def _plural(count: int, singular: str, plural: str) -> str:
    """Render ``count`` with the number-appropriate noun."""
    return f"{count} {singular}" if count == 1 else f"{count} {plural}"


def _counted(messages: list[str]) -> list[tuple[str, int]]:
    """Collapse repeated report lines into ``(message, count)`` pairs.

    A 48-port switch whose every interface shadows the same field would
    otherwise emit 48 identical lines and bury the rest of the report.
    """
    counts: dict[str, int] = {}
    for message in messages:
        counts[message] = counts.get(message, 0) + 1
    return list(counts.items())


# --------------------------------------------------------------------------
# Conversion
# --------------------------------------------------------------------------


@dataclass
class Coverage:
    """What a single device-type conversion emitted, skipped, and coerced.

    Args:
        slug: The NetBox slug of the converted device type.
        source: Path the definition was read from.
        template_name: The emitted parent template name.
        converted: Component list name to number of emitted templates.
        skipped_lists: Component list name to number of skipped entries.
        dropped_fields: Owner (``device_type`` or a list name) to dropped keys.
        notes: Free-text coercion notes.
        shadowed: Values lost because a higher-priority fallback source won.
    """

    slug: str
    source: Path
    template_name: str
    converted: dict[str, int] = field(default_factory=dict)
    skipped_lists: dict[str, int] = field(default_factory=dict)
    dropped_fields: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    shadowed: list[str] = field(default_factory=list)
    input_kind: str = DEVICE_TYPES

    @property
    def is_lossless(self) -> bool:
        """True when nothing was skipped, dropped, or shadowed."""
        return not self.skipped_lists and not self.dropped_fields and not self.shadowed


@dataclass
class Conversion:
    """The full result of converting a batch of NetBox definitions."""

    manufacturers: list[dict[str, Any]] = field(default_factory=list)
    device_types: list[dict[str, Any]] = field(default_factory=list)
    templates: list[dict[str, Any]] = field(default_factory=list)
    module_types: list[dict[str, Any]] = field(default_factory=list)
    module_templates: list[dict[str, Any]] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)


def _build_type_object(
    source_type: DeviceType,
    *,
    fields: tuple[FieldMapping, ...],
    defaults: dict[str, Any],
    manufacturer_relationship: str,
    top_level_fields: tuple[str, ...],
    extra_consumed: set[str],
    coverage: Coverage,
    owner: str,
) -> dict[str, Any]:
    """Build the Infrahub type object for one NetBox definition.

    Device types and module types differ only in which kind and fields they
    target, so both go through here.

    Args:
        source_type: The parsed NetBox definition.
        fields: Field mappings to apply.
        defaults: Attributes written when not otherwise set.
        manufacturer_relationship: Relationship naming the manufacturer.
        top_level_fields: The NetBox field inventory to check for drops.
        extra_consumed: Fields consumed elsewhere (e.g. by a name format).
        coverage: Collector for notes, shadowing, and dropped fields.
        owner: Label used in the coverage report.

    Returns:
        The Infrahub object as a mapping.
    """
    obj: dict[str, Any] = {}
    for mapping in fields:
        source, raw, shadowed = resolve_source(mapping, source_type.data)
        if source is None:
            continue
        value, note = apply_transform(mapping, raw, source_type.data)
        obj[mapping.target] = value
        if note:
            coverage.notes.append(f"{source}: {note}")
        coverage.shadowed.extend(
            f"{owner} `{name}` lost to `{source}` on `{mapping.target}`" for name in shadowed
        )
    obj[manufacturer_relationship] = source_type.manufacturer
    for key, value in defaults.items():
        obj.setdefault(key, value)

    # `manufacturer` becomes its own object, `weight_unit` is folded into the
    # weight conversion, and name-format fields identify the record — none of
    # those are lost, so none belong in the dropped-field report.
    consumed = (
        {name for mapping in fields for name in mapping.sources}
        | {"manufacturer", "weight_unit"}
        | extra_consumed
    )
    dropped = [
        key
        for key in source_type.data
        if key in top_level_fields and key not in consumed and source_type.data[key] is not None
    ]
    if dropped:
        coverage.dropped_fields[owner] = sorted(dropped)
    return obj


def _build_device_type(device: DeviceType, profile: Profile, coverage: Coverage) -> dict[str, Any]:
    """Build the Infrahub device-type object for one NetBox definition."""
    return _build_type_object(
        device,
        fields=profile.device_type_fields,
        defaults=profile.device_type_defaults,
        manufacturer_relationship=profile.device_type_manufacturer_rel,
        top_level_fields=NETBOX_TOP_LEVEL_FIELDS,
        extra_consumed=format_fields(profile.template_name_format),
        coverage=coverage,
        owner="device_type",
    )


def _build_component(
    component: ComponentMapping,
    entry: dict[str, Any],
    template_name: str,
    coverage: Coverage,
) -> dict[str, Any]:
    """Build one Infrahub component template from a NetBox component entry."""
    obj: dict[str, Any] = {
        "template_name": _format_name(
            component.template_name, {**entry, "template_name": template_name}
        )
    }
    for mapping in component.fields:
        source, raw, shadowed = resolve_source(mapping, entry)
        if source is None:
            continue
        value, note = apply_transform(mapping, raw, entry)
        obj[mapping.target] = value
        if note:
            coverage.notes.append(f"{component.netbox_list}.{source}: {note}")
        coverage.shadowed.extend(
            f"{component.netbox_list} `{name}` lost to `{source}` on `{mapping.target}`"
            for name in shadowed
        )

    for derived in component.derived:
        if _matches(entry, derived.when):
            obj[derived.target] = derived.value

    for key, value in component.defaults.items():
        obj.setdefault(key, value)
    return obj


def _attach_component_block(
    template: dict[str, Any], component: ComponentMapping, children: list[dict[str, Any]]
) -> None:
    """Attach one component block to its relationship on the template.

    Several NetBox lists can legitimately land on a single Infrahub
    relationship — a schema whose console-port node inherits the interface
    generic takes both ``interfaces`` and ``console-ports`` on its
    ``interfaces`` relationship. Assigning would make the second mapping
    silently erase the first, so blocks accumulate into the list form the
    object loader resolves per item.

    The single-mapping case keeps the plain ``{kind, data}`` mapping, which
    is the common shape and the more readable one.
    """
    block = {"kind": component.kind, "data": children}
    existing = template.get(component.relationship)
    if existing is None:
        template[component.relationship] = block
    elif isinstance(existing, dict):
        template[component.relationship] = [existing, block]
    else:
        existing.append(block)


def _record_dropped_component_fields(
    component: ComponentMapping, entries: list[dict[str, Any]], coverage: Coverage
) -> None:
    """Record NetBox component keys the profile does not map."""
    consumed = (
        {name for mapping in component.fields for name in mapping.sources}
        | {key for derived in component.derived for key in derived.when}
        | format_fields(component.template_name)
    )
    dropped = {
        key
        for entry in entries
        for key, value in entry.items()
        if key not in consumed and value is not None
    }
    if dropped:
        coverage.dropped_fields[component.netbox_list] = sorted(dropped)


def convert_device_type(device: DeviceType, profile: Profile) -> tuple[dict[str, Any], Coverage]:
    """Convert one NetBox device type into an Infrahub object template.

    Args:
        device: The parsed NetBox device type.
        profile: The mapping profile describing the target schema.

    Returns:
        A ``(template_object, coverage)`` pair. The device-type object is
        stored on the returned coverage's caller via ``convert_all``.

    Raises:
        ConversionError: If a ``template_name`` format string is invalid.
    """
    template_name = _format_name(profile.template_name_format, dict(device.data))
    coverage = Coverage(slug=device.slug, source=device.source, template_name=template_name)

    template: dict[str, Any] = {
        "template_name": template_name,
        profile.template_device_type_rel: device.model,
    }
    for key, value in profile.template_defaults.items():
        template.setdefault(key, value)

    for component in profile.components:
        entries = device.components(component.netbox_list)
        if not entries:
            continue
        children = [
            _build_component(component, entry, template_name, coverage) for entry in entries
        ]
        _attach_component_block(template, component, children)
        coverage.converted[component.netbox_list] = len(children)
        _record_dropped_component_fields(component, entries, coverage)

    for list_name in NETBOX_COMPONENT_LISTS:
        if list_name in profile.mapped_lists:
            continue
        entries = device.components(list_name)
        if entries:
            coverage.skipped_lists[list_name] = len(entries)

    return template, coverage


def _substitute_position(value: Any, placeholder: str | None) -> Any:
    """Resolve or preserve the NetBox ``{module}`` position token."""
    if placeholder is None or not isinstance(value, str):
        return value
    return value.replace(MODULE_POSITION_TOKEN, placeholder)


def convert_module_type(
    module: DeviceType, target: ModuleTarget
) -> tuple[dict[str, Any], dict[str, Any] | None, Coverage]:
    """Convert one NetBox module type into Infrahub objects.

    Args:
        module: The parsed NetBox module type.
        target: The ``module_type`` section of the mapping profile.

    Returns:
        A ``(module_type_object, module_template_or_None, coverage)`` triple.

    Raises:
        ConversionError: If a format string references an unknown field.
    """
    key = _format_name(target.key_format, dict(module.data))
    coverage = Coverage(slug=key, source=module.source, template_name=key, input_kind=MODULE_TYPES)

    obj = _build_type_object(
        module,
        fields=target.fields,
        defaults=target.defaults,
        manufacturer_relationship=target.manufacturer_relationship,
        top_level_fields=NETBOX_MODULE_TOP_LEVEL_FIELDS,
        extra_consumed=format_fields(target.key_format),
        coverage=coverage,
        owner="module_type",
    )

    template: dict[str, Any] | None = None
    if target.emits_templates:
        template_name = _format_name(str(target.template_name_format), dict(module.data))
        coverage.template_name = template_name
        template = {"template_name": template_name}
        if target.template_type_relationship:
            template[target.template_type_relationship] = key
        for name, value in target.template_defaults.items():
            template.setdefault(name, value)

        for component in target.components:
            entries = module.components(component.netbox_list)
            if not entries:
                continue
            children = [
                _build_component(
                    component,
                    _resolve_entry_positions(entry, target.position_placeholder),
                    template_name,
                    coverage,
                )
                for entry in entries
            ]
            _attach_component_block(template, component, children)
            coverage.converted[component.netbox_list] = len(children)
            _record_dropped_component_fields(component, entries, coverage)

        if target.position_placeholder is None:
            unresolved = sum(
                1
                for component in target.components
                for entry in module.components(component.netbox_list)
                if MODULE_POSITION_TOKEN in str(entry.get("name", ""))
            )
            if unresolved:
                coverage.notes.append(
                    f"{_plural(unresolved, 'component name', 'component names')} keep the "
                    f"literal {MODULE_POSITION_TOKEN} bay-position token; set "
                    "module_type.position_placeholder to substitute it"
                )

    mapped = target.mapped_lists if target.emits_templates else set()
    for list_name in NETBOX_COMPONENT_LISTS:
        if list_name in mapped:
            continue
        entries = module.components(list_name)
        if entries:
            coverage.skipped_lists[list_name] = len(entries)

    return obj, template, coverage


def _resolve_entry_positions(entry: dict[str, Any], placeholder: str | None) -> dict[str, Any]:
    """Return a component entry with ``{module}`` resolved where configured."""
    if placeholder is None:
        return entry
    return {key: _substitute_position(value, placeholder) for key, value in entry.items()}


def convert_all(devices: list[DeviceType], profile: Profile) -> Conversion:
    """Convert a batch of device types, de-duplicating manufacturers.

    Args:
        devices: Parsed NetBox device types, in the order they were read.
        profile: The mapping profile describing the target schema.

    Returns:
        The aggregated conversion result.

    Raises:
        ConversionError: If two definitions produce the same template name.
    """
    result = Conversion()
    seen_manufacturers: set[str] = set()
    seen_names: dict[str, Path] = {}

    modules = [device for device in devices if device.is_module]
    if modules and profile.modules is None:
        raise ConversionError(
            f"{len(modules)} module-type file(s) matched (for example {modules[0].source}), "
            f"but mapping profile {profile.name!r} has no 'module_type' section. Add one, "
            "or point the converter at device-types only."
        )

    for entry in devices:
        if entry.is_module:
            target = profile.modules
            assert target is not None  # guarded above
            obj, template, coverage = convert_module_type(entry, target)
            _claim_name(seen_names, coverage.template_name, entry.source, "module")
            result.module_types.append(obj)
            if template is not None:
                result.module_templates.append(template)
        else:
            template, coverage = convert_device_type(entry, profile)
            _claim_name(seen_names, template["template_name"], entry.source, "template")
            result.device_types.append(_build_device_type(entry, profile, coverage))
            result.templates.append(template)

        if entry.manufacturer not in seen_manufacturers:
            seen_manufacturers.add(entry.manufacturer)
            result.manufacturers.append({profile.manufacturer_name_field: entry.manufacturer})
        result.coverage.append(coverage)

    result.manufacturers.sort(key=lambda obj: obj[profile.manufacturer_name_field])
    return result


def _claim_name(seen: dict[str, Path], name: str, source: Path, label: str) -> None:
    """Reserve an identity, refusing a collision rather than emitting both."""
    if name in seen:
        raise ConversionError(
            f"{source}: {label} name {name!r} already produced by {seen[name]}; "
            f"{label} names must be unique"
        )
    seen[name] = source


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render_object_file(kind: str, data: list[dict[str, Any]]) -> str:
    """Render one Infrahub object file.

    Args:
        kind: The Infrahub node kind for ``spec.kind``.
        data: The object rows for ``spec.data``.

    Returns:
        The YAML document, including the ``---`` marker and schema hint.
    """
    document = {
        "apiVersion": "infrahub.app/v1",
        "kind": "Object",
        "spec": {"kind": kind, "data": data},
    }
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )
    return f"---\n{body}"


def _render_coverage_row(entry: Coverage) -> str:
    """Render one device type's row in the report summary table."""
    converted = ", ".join(f"{name} ({count})" for name, count in sorted(entry.converted.items()))
    skipped = ", ".join(f"{name} ({count})" for name, count in sorted(entry.skipped_lists.items()))
    kind = "module" if entry.input_kind == MODULE_TYPES else "device"
    return (
        f"| `{entry.slug}` | {kind} | {converted or '—'} | {skipped or '—'} | "
        f"{'yes' if entry.is_lossless else 'no'} |"
    )


#: Where a reader goes to turn a reported gap into a schema change.
EXTENDING_GUIDE = "extending-your-schema.md"

DOCS_SCHEMA_EXTENSIONS = "https://docs.infrahub.app/schema/extensions"
DOCS_RELATIONSHIPS = "https://docs.infrahub.app/schema/relationships"
DOCS_ATTRIBUTES = "https://docs.infrahub.app/schema/nodes-and-attributes"


def _render_gap_guidance(conversion: Conversion) -> list[str]:
    """Explain what each kind of gap means and how it is closed.

    A bare "Skipped console-ports" is only actionable to someone who
    already knows Infrahub generates component templates from Component
    relationships. This section states the reason and points at the fix.
    """
    skipped: set[str] = set()
    dropped: set[str] = set()
    shadowed = 0
    for entry in conversion.coverage:
        skipped.update(entry.skipped_lists)
        for owner, keys in entry.dropped_fields.items():
            dropped.update(f"{owner}.{key}" for key in keys)
        shadowed += len(entry.shadowed)

    if not (skipped or dropped or shadowed):
        return []

    lines = ["", "## Closing these gaps", ""]
    if skipped:
        lines.extend(
            [
                f"**Skipped component lists** ({', '.join(f'`{n}`' for n in sorted(skipped))})",
                "— the target schema has no node for these, so Infrahub has",
                "nothing to generate a component template from. Each one needs a",
                "node plus a `Component`/`Parent` relationship pair joining it to",
                f"the device, then an entry in the mapping profile. See {DOCS_RELATIONSHIPS}",
                "",
            ]
        )
    if dropped:
        shown = ", ".join(f"`{name}`" for name in sorted(dropped)[:8])
        more = "" if len(dropped) <= 8 else f" (and {len(dropped) - 8} more)"
        lines.extend(
            [
                f"**Dropped fields** ({shown}{more}) — the node exists but has no",
                "attribute to hold the value. Each needs one attribute added, most",
                f"simply via a schema extension. See {DOCS_ATTRIBUTES}",
                "",
            ]
        )
    if shadowed:
        lines.extend(
            [
                f"**Shadowed values** ({shadowed}) — two NetBox fields competed for",
                "one Infrahub attribute and the lower-priority one was discarded.",
                "Give the loser its own attribute, or accept the loss knowingly.",
                "",
            ]
        )
    lines.extend(
        [
            f"Worked YAML for each case is in the skill's `{EXTENDING_GUIDE}`.",
            "Schema extensions keep these additions separable from an upstream",
            f"schema library: {DOCS_SCHEMA_EXTENSIONS}",
            "",
            "Closing a gap is optional. A component you never query is cost, not",
            "completeness — leaving it reported is a valid permanent answer.",
        ]
    )
    return lines


def render_report(conversion: Conversion, profile: Profile) -> str:
    """Render the Markdown coverage report.

    Args:
        conversion: The aggregated conversion result.
        profile: The mapping profile that was applied.

    Returns:
        A Markdown report naming every skipped component list, dropped
        field, and value coercion.
    """
    devices = [e for e in conversion.coverage if e.input_kind == DEVICE_TYPES]
    modules = [e for e in conversion.coverage if e.input_kind == MODULE_TYPES]
    lines = [
        "# NetBox to Infrahub conversion coverage",
        "",
        f"Mapping profile: `{profile.name}`",
        f"Device types converted: {len(devices)}",
    ]
    if modules:
        lines.append(f"Module types converted: {len(modules)}")
    lines.extend(
        [
            "",
            "| Source | Kind | Converted components | Skipped components | Lossless |",
            "| ------ | ---- | -------------------- | ------------------ | -------- |",
        ]
    )
    lines.extend(_render_coverage_row(entry) for entry in conversion.coverage)

    lossy = [entry for entry in conversion.coverage if not entry.is_lossless or entry.notes]
    if not lossy:
        lines.extend(["", "Every field of every input mapped onto the target schema."])
        return "\n".join(lines) + "\n"

    lines.extend(_render_gap_guidance(conversion))
    lines.extend(["", "## Details", ""])
    for entry in lossy:
        lines.append(f"### `{entry.slug}`")
        lines.append("")
        lines.append(f"Source: `{entry.source}`")
        lines.append("")
        for list_name, count in sorted(entry.skipped_lists.items()):
            lines.append(
                f"- Skipped `{list_name}` ({_plural(count, 'entry', 'entries')})"
                " — not mapped by the profile"
            )
        for owner, keys in sorted(entry.dropped_fields.items()):
            lines.append(f"- Dropped from `{owner}`: {', '.join(f'`{k}`' for k in keys)}")
        for shadow, count in _counted(entry.shadowed):
            occurrences = "" if count == 1 else f" ({count} entries)"
            lines.append(f"- Shadowed: {shadow}{occurrences} — both were set")
        for note, count in _counted(entry.notes):
            occurrences = "" if count == 1 else f" ({count} entries)"
            lines.append(f"- Coerced {note}{occurrences}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_outputs(conversion: Conversion, profile: Profile, output_dir: Path) -> list[Path]:
    """Write the three object files in load order.

    Args:
        conversion: The aggregated conversion result.
        profile: The mapping profile that was applied.
        output_dir: Directory to write into; created if absent.

    Returns:
        The paths written, in load order.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    modules = profile.modules
    payloads: list[tuple[str, str | None, list[dict[str, Any]]]] = [
        (OUTPUT_FILENAMES["manufacturer"], profile.manufacturer_kind, conversion.manufacturers),
        (OUTPUT_FILENAMES["device_type"], profile.device_type_kind, conversion.device_types),
        (OUTPUT_FILENAMES["template"], profile.template_kind, conversion.templates),
        (
            OUTPUT_FILENAMES["module_type"],
            modules.kind if modules else None,
            conversion.module_types,
        ),
        (
            OUTPUT_FILENAMES["module_template"],
            modules.template_kind if modules else None,
            conversion.module_templates,
        ),
    ]
    written: list[Path] = []
    for filename, kind, data in payloads:
        # Skip a slot with nothing in it: converting only module types
        # should not leave empty device files behind, and an empty
        # spec.data is noise the loader would still walk.
        if not data or not kind:
            continue
        path = output_dir / filename
        path.write_text(render_object_file(kind, data), encoding="utf-8")
        written.append(path)
    return written


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="netbox_to_infrahub_templates.py",
        description="Convert NetBox device types into Infrahub object templates.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="NetBox device-type YAML files, directories, or glob patterns.",
    )
    parser.add_argument(
        "--mapping",
        required=True,
        type=Path,
        help="Mapping profile describing the target Infrahub schema.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write the generated object files into.",
    )
    parser.add_argument(
        "--report",
        default="coverage-report.md",
        help="Coverage report path, or '-' to write it to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the converter.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    try:
        profile = load_profile(args.mapping)
        files = iter_input_files(args.inputs)
        if not files:
            print("No NetBox device-type files matched the given inputs.", file=sys.stderr)
            return 2
        devices = [parse_device_type(path) for path in files]
        conversion = convert_all(devices, profile)
        written = write_outputs(conversion, profile, args.output_dir)
        report = render_report(conversion, profile)
    except ConversionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.report == "-":
        print(report)
    else:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        written.append(report_path)

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
