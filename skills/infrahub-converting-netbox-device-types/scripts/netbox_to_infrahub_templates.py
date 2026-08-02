#!/usr/bin/env python3
"""Convert NetBox device-type definitions into Infrahub object template YAML.

Reads one or more NetBox ``devicetype-library`` YAML files (the format
published at https://github.com/netbox-community/devicetype-library and
browsable via the NetBox Data Exchange) and emits Infrahub object files:

1. Manufacturer objects
2. Device type objects (which carry the physical model data)
3. Object templates (``Template<Kind>``) plus their nested component
   templates

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

#: Fields required by the NetBox device-type JSON schema.
NETBOX_REQUIRED_FIELDS: tuple[str, ...] = ("manufacturer", "model", "slug")

#: Conversion factors from each NetBox weight unit to kilograms.
WEIGHT_TO_KG: dict[str, float] = {
    "kg": 1.0,
    "g": 0.001,
    "lb": 0.45359237,
    "oz": 0.028349523125,
}

SUPPORTED_TRANSFORMS: tuple[str, ...] = ("text", "number", "boolean", "weight_kg")

OUTPUT_FILENAMES: dict[str, str] = {
    "manufacturer": "01_manufacturers.yml",
    "device_type": "02_device_types.yml",
    "template": "03_device_templates.yml",
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


def _parse_components(raw: Any) -> tuple[ComponentMapping, ...]:
    """Parse the ``components:`` block of a mapping profile."""
    components: list[ComponentMapping] = []
    for netbox_list, spec in _require_mapping(raw or {}, "components").items():
        path = f"components.{netbox_list}"
        if netbox_list not in NETBOX_COMPONENT_LISTS:
            raise ConversionError(
                f"Mapping profile: '{path}' is not a NetBox component list "
                f"({', '.join(NETBOX_COMPONENT_LISTS)})"
            )
        spec_map = _require_mapping(spec, path)
        for required in ("kind", "relationship", "template_name"):
            if not spec_map.get(required):
                raise ConversionError(f"Mapping profile: '{path}' needs '{required}'")
        components.append(
            ComponentMapping(
                netbox_list=netbox_list,
                kind=spec_map["kind"],
                relationship=spec_map["relationship"],
                template_name=spec_map["template_name"],
                fields=_parse_fields(spec_map.get("fields"), f"{path}.fields"),
                derived=_parse_derived(spec_map.get("derived"), f"{path}.derived"),
                defaults=dict(_require_mapping(spec_map.get("defaults", {}), f"{path}.defaults")),
            )
        )
    return tuple(components)


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
    )


# --------------------------------------------------------------------------
# NetBox input
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceType:
    """A parsed NetBox device-type definition.

    Args:
        source: Path the definition was read from.
        data: The raw parsed YAML mapping.
    """

    source: Path
    data: dict[str, Any]

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
        """The NetBox slug, unique across the library."""
        return str(self.data["slug"])

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

    missing = [key for key in NETBOX_REQUIRED_FIELDS if not raw.get(key)]
    if missing:
        raise ConversionError(f"{path}: missing required NetBox field(s): {', '.join(missing)}")

    return DeviceType(source=path, data=raw)


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

    @property
    def is_lossless(self) -> bool:
        """True when nothing was skipped, dropped, or shadowed."""
        return not self.skipped_lists and not self.dropped_fields and not self.shadowed


@dataclass
class Conversion:
    """The full result of converting a batch of device types."""

    manufacturers: list[dict[str, Any]] = field(default_factory=list)
    device_types: list[dict[str, Any]] = field(default_factory=list)
    templates: list[dict[str, Any]] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)


def _build_device_type(device: DeviceType, profile: Profile, coverage: Coverage) -> dict[str, Any]:
    """Build the Infrahub device-type object for one NetBox definition."""
    obj: dict[str, Any] = {}
    for mapping in profile.device_type_fields:
        source, raw, shadowed = resolve_source(mapping, device.data)
        if source is None:
            continue
        value, note = apply_transform(mapping, raw, device.data)
        obj[mapping.target] = value
        if note:
            coverage.notes.append(f"{source}: {note}")
        coverage.shadowed.extend(
            f"device_type `{name}` lost to `{source}` on `{mapping.target}`" for name in shadowed
        )
    obj[profile.device_type_manufacturer_rel] = device.manufacturer
    for key, value in profile.device_type_defaults.items():
        obj.setdefault(key, value)

    # `manufacturer` becomes its own object, `weight_unit` is folded into the
    # weight conversion, and template-name fields identify the template — none
    # of those are lost, so none belong in the dropped-field report.
    consumed = (
        {name for mapping in profile.device_type_fields for name in mapping.sources}
        | {"manufacturer", "weight_unit"}
        | format_fields(profile.template_name_format)
    )
    dropped = [
        key
        for key in device.data
        if key in NETBOX_TOP_LEVEL_FIELDS and key not in consumed and device.data[key] is not None
    ]
    if dropped:
        coverage.dropped_fields["device_type"] = sorted(dropped)
    return obj


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
        template[component.relationship] = {"kind": component.kind, "data": children}
        coverage.converted[component.netbox_list] = len(children)
        _record_dropped_component_fields(component, entries, coverage)

    for list_name in NETBOX_COMPONENT_LISTS:
        if list_name in profile.mapped_lists:
            continue
        entries = device.components(list_name)
        if entries:
            coverage.skipped_lists[list_name] = len(entries)

    return template, coverage


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
    seen_templates: dict[str, Path] = {}

    for device in devices:
        template, coverage = convert_device_type(device, profile)
        if template["template_name"] in seen_templates:
            first = seen_templates[template["template_name"]]
            raise ConversionError(
                f"{device.source}: template_name {template['template_name']!r} "
                f"already produced by {first}; template names must be unique"
            )
        seen_templates[template["template_name"]] = device.source

        if device.manufacturer not in seen_manufacturers:
            seen_manufacturers.add(device.manufacturer)
            result.manufacturers.append({profile.manufacturer_name_field: device.manufacturer})

        result.device_types.append(_build_device_type(device, profile, coverage))
        result.templates.append(template)
        result.coverage.append(coverage)

    result.manufacturers.sort(key=lambda obj: obj[profile.manufacturer_name_field])
    return result


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
    return (
        f"| `{entry.slug}` | {converted or '—'} | {skipped or '—'} | "
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
    lines = [
        "# NetBox to Infrahub conversion coverage",
        "",
        f"Mapping profile: `{profile.name}`",
        f"Device types converted: {len(conversion.coverage)}",
        "",
        "| Device type | Converted components | Skipped components | Lossless |",
        "| ----------- | -------------------- | ------------------ | -------- |",
    ]
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
    payloads = (
        (OUTPUT_FILENAMES["manufacturer"], profile.manufacturer_kind, conversion.manufacturers),
        (OUTPUT_FILENAMES["device_type"], profile.device_type_kind, conversion.device_types),
        (OUTPUT_FILENAMES["template"], profile.template_kind, conversion.templates),
    )
    written: list[Path] = []
    for filename, kind, data in payloads:
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
