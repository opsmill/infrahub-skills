#!/usr/bin/env python3
"""Export device and module types from a live NetBox into library YAML.

``netbox_to_infrahub_templates.py`` reads the netbox-community
``devicetype-library`` file format. A running NetBox holds the same
information in its database, shaped for its REST API instead, so the two do
not meet without a step in between. This is that step: it reads a live
instance and writes files the converter accepts.

The two together give the full path from a running NetBox to Infrahub
object templates::

    netbox_export_device_types.py --url ... --output-dir ./device-types
    netbox_to_infrahub_templates.py ./device-types --mapping ... --output-dir ./generated

This is **not** a sync. It is a one-way snapshot into files you can read,
diff, and keep. Continuous replication between a live NetBox and Infrahub is
`infrahub-sync <https://docs.infrahub.app/sync/>`_, a separate product.

Reading through pynetbox
------------------------
The official client handles pagination, auth, retries and TLS, and tracks the
API as it changes across NetBox versions. Fields are read as **attributes**,
not via ``Record.serialize()``: serialising flattens a related object to its
primary key, so an outlet's ``power_port`` would become ``16`` where the
library format needs the port's name.

Everything downstream of the client works on plain mappings or pynetbox
records interchangeably (see ``field``), which keeps the reshaping testable
without a server while leaving the live path on the real client.

Shape differences this has to reconcile
---------------------------------------
The REST API is not the library format, and four differences matter:

* Choice fields serialize as ``{"value": ..., "label": ...}``. The library
  wants the bare value, so every choice is unwrapped.
* Decimals (``weight``, ``u_height``) may arrive as strings. They are
  coerced back to numbers.
* Related objects are nested documents. ``manufacturer`` becomes its name.
* Front/rear port mappings are a many-to-many carrying positions on both
  ends, keyed by primary key. They are resolved back to port *names* and
  emitted as the library's ``port-mappings`` list.

Anything the API reports that has no place in the library format is counted
and named at the end, on the same principle as the converter's coverage
report: a silent omission is worse than a stated one.

Usage
-----
::

    export NETBOX_TOKEN=...
    python netbox_export_device_types.py \\
        --url https://netbox.example.com \\
        --output-dir ./device-types

    # only what is actually racked, which is usually what you want
    python netbox_export_device_types.py --url ... --in-use --output-dir ./device-types

    # a single vendor, plus the module types that go in them
    python netbox_export_device_types.py --url ... \\
        --manufacturer arista --module-types --output-dir ./netbox-export

Exit codes
----------
0
    Export completed.
1
    Configuration, network, or authentication failure.
2
    Nothing matched the given filters.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# NetBox API constants
# --------------------------------------------------------------------------

DEVICE_TYPES = "dcim.device_types"
MODULE_TYPES = "dcim.module_types"

#: NetBox component-template endpoints, paired with the devicetype-library
#: list each one becomes. Order matches the library's own field order so the
#: emitted files read like the published ones.
DEVICE_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("dcim.console_port_templates", "console-ports"),
    ("dcim.console_server_port_templates", "console-server-ports"),
    ("dcim.power_port_templates", "power-ports"),
    ("dcim.power_outlet_templates", "power-outlets"),
    ("dcim.interface_templates", "interfaces"),
    ("dcim.front_port_templates", "front-ports"),
    ("dcim.rear_port_templates", "rear-ports"),
    ("dcim.module_bay_templates", "module-bays"),
    ("dcim.device_bay_templates", "device-bays"),
    ("dcim.inventory_item_templates", "inventory-items"),
)

#: A module type has no bays of its own to fill, and no device bays.
MODULE_COMPONENT_LISTS = frozenset(
    {
        "console-ports",
        "console-server-ports",
        "power-ports",
        "power-outlets",
        "interfaces",
        "front-ports",
        "rear-ports",
        "module-bays",
    }
)

#: Per library list, the entry fields to carry and in what order. Taken from
#: the devicetype-library JSON schema (``schema/components.json``); anything
#: outside this is reported rather than invented.
COMPONENT_FIELDS: dict[str, tuple[str, ...]] = {
    "console-ports": ("name", "label", "type", "description"),
    "console-server-ports": ("name", "label", "type", "description"),
    "power-ports": (
        "name",
        "label",
        "type",
        "maximum_draw",
        "allocated_draw",
        "description",
    ),
    "power-outlets": ("name", "label", "type", "power_port", "feed_leg", "description"),
    "interfaces": (
        "name",
        "label",
        "type",
        "enabled",
        "mgmt_only",
        "description",
        "bridge",
        "poe_mode",
        "poe_type",
        "rf_role",
    ),
    "front-ports": ("name", "label", "type", "color", "positions", "description"),
    "rear-ports": ("name", "label", "type", "color", "positions", "description"),
    "module-bays": ("name", "label", "position", "description"),
    "device-bays": ("name", "label", "description"),
    "inventory-items": ("name", "label", "manufacturer", "part_id", "description"),
}

#: Device-type fields carried to the library format, in the library's order.
DEVICE_TYPE_FIELDS: tuple[str, ...] = (
    "manufacturer",
    "model",
    "slug",
    "part_number",
    "u_height",
    "is_full_depth",
    "airflow",
    "weight",
    "weight_unit",
    "subdevice_role",
    "front_image",
    "rear_image",
    "description",
    "comments",
)

#: Module types carry no slug and no rack geometry.
MODULE_TYPE_FIELDS: tuple[str, ...] = (
    "manufacturer",
    "model",
    "part_number",
    "airflow",
    "weight",
    "weight_unit",
    "description",
    "comments",
)

#: Fields the devicetype-library schema requires, per list. A NetBox object
#: can legitimately lack these — a power port with no type is valid in NetBox
#: and invalid in the library — so they are reported, never invented.
REQUIRED_COMPONENT_FIELDS: dict[str, tuple[str, ...]] = {
    "console-ports": ("name", "type"),
    "console-server-ports": ("name", "type"),
    "power-ports": ("name", "type"),
    "power-outlets": ("name", "type"),
    "interfaces": ("name", "type"),
    "front-ports": ("name", "type", "positions"),
    "rear-ports": ("name", "type", "positions"),
    "module-bays": ("name", "position"),
    "device-bays": ("name",),
    "inventory-items": ("name",),
}

#: Top-level fields the library schema requires of a device type.
REQUIRED_DEVICE_TYPE_FIELDS: tuple[str, ...] = (
    "manufacturer",
    "model",
    "slug",
    "u_height",
    "is_full_depth",
)

#: Fields the library schema requires of a module type.
REQUIRED_MODULE_TYPE_FIELDS: tuple[str, ...] = ("manufacturer", "model")

#: Fields that are numeric in the library format. NetBox may serialize a
#: DecimalField as a string, which YAML would then quote.
NUMERIC_FIELDS = frozenset(
    {"u_height", "weight", "maximum_draw", "allocated_draw", "positions"}
)

#: How many object ids to request per component-template call. NetBox accepts
#: a repeated ``device_type_id``, so components for many device types come
#: back in one round trip; the cap keeps the URL inside the 2048 characters
#: some proxies still enforce.
#:
#: This makes a *full* export chatty: 5,900 device types is ~120 batches
#: across ten endpoints, so roughly 1,200 calls. Dropping the filter would
#: make it ten calls plus pagination, but then every component in the
#: instance is fetched even when exporting a handful of device types, and
#: choosing between the two needs a heuristic that is wrong somewhere. The
#: filtered path is predictable and is the one ``--in-use`` puts you on,
#: which is the recommended way to run this.
ID_BATCH = 50


class ExportError(Exception):
    """Raised when the export cannot proceed."""


# --------------------------------------------------------------------------
# NetBox access
# --------------------------------------------------------------------------


class Source(Protocol):
    """The reading surface this exporter needs from NetBox.

    Narrowing pynetbox to one method keeps the export logic testable against
    canned data: a test supplies mappings, the live path supplies pynetbox
    records, and everything downstream reads both through ``field``.
    """

    def records(self, endpoint: str, **filters: Any) -> Iterable[Any]:
        """Return every object at ``endpoint`` matching ``filters``."""
        ...  # pragma: no cover - protocol


class NetBoxSource:
    """Reads a live NetBox through pynetbox.

    Args:
        url: Base URL of the instance, without ``/api``.
        token: API token.
        verify: Whether to verify TLS certificates.
        timeout: Per-request timeout in seconds.
    """

    #: Endpoints absent from this NetBox, reported once rather than per call.
    missing_endpoints: set[str]

    def __init__(self, url: str, token: str, *, verify: bool = True, timeout: float = 30.0):
        try:
            import pynetbox
        except ImportError as exc:  # pragma: no cover - environment guard
            raise ExportError("pynetbox is required: pip install pynetbox") from exc

        self._api = pynetbox.api(url.rstrip("/"), token=token)
        session = self._api.http_session
        session.verify = verify
        # pynetbox has no timeout setting of its own, so wrap the session's
        # request method. Without this --timeout parses and does nothing, and
        # a NetBox that accepts the connection then stalls hangs the export.
        original = session.request

        def _with_timeout(method: str, url_: str, **kwargs: Any) -> Any:
            kwargs.setdefault("timeout", timeout)
            return original(method, url_, **kwargs)

        session.request = _with_timeout  # type: ignore[method-assign]
        self._timeout = timeout
        self._url = url
        self.missing_endpoints = set()
        self._reached = False

    def records(self, endpoint: str, **filters: Any) -> Iterator[Any]:
        """Yield every record at ``endpoint``, following pagination.

        Args:
            endpoint: Dotted pynetbox endpoint, e.g. ``dcim.device_types``.
            **filters: Query filters. A list value becomes a repeated
                parameter, which is how one call covers many parent ids.

        Yields:
            pynetbox records.

        Raises:
            ExportError: With a message naming the likely cause, since a bare
                pynetbox traceback rarely says whether the token, the URL or
                the network is at fault. An endpoint this NetBox does not have
                is recorded and skipped instead: component endpoints come and
                go across NetBox versions, and losing one list is not a reason
                to lose the whole export.
        """
        app, name = endpoint.split(".", 1)
        try:
            source = getattr(getattr(self._api, app), name)
            for record in source.filter(**filters) if filters else source.all():
                self._reached = True
                yield record
        except Exception as exc:  # noqa: BLE001 - re-raised with context below
            # A 404 is ambiguous: this NetBox may not have the endpoint, or
            # --url may be wrong. Treat it as "absent" only once something has
            # answered, so a bad URL fails loudly instead of exporting nothing.
            if self._is_missing_endpoint(exc) and self._reached:
                self.missing_endpoints.add(endpoint)
                return
            raise ExportError(self._explain(exc, endpoint)) from exc
        self._reached = True

    @staticmethod
    def _is_missing_endpoint(exc: Exception) -> bool:
        """True when the failure is 'this NetBox has no such endpoint'."""
        text = str(exc)
        return "could not be found" in text or "404" in text

    def _explain(self, exc: Exception, endpoint: str) -> str:
        """Turn a client or transport error into something actionable."""
        text = str(exc)
        if "403" in text or "401" in text or "Invalid token" in text:
            return (
                f"NetBox rejected the token. Check --token / NETBOX_TOKEN, and that "
                f"it grants read access to {endpoint.split('.', 1)[0]}."
            )
        if self._is_missing_endpoint(exc):
            # Reached only before anything has answered, so the endpoint being
            # absent is far less likely than --url being wrong.
            return (
                f"{self._url} returned 404 for {endpoint}. Is --url the base URL of the "
                "instance, without a trailing /api? pynetbox appends that itself."
            )
        if "SSLError" in type(exc).__name__ or "certificate" in text.lower():
            return f"TLS verification failed for {self._url}. Pass --insecure for a self-signed cert."
        return f"Reading {endpoint} from {self._url} failed: {text}"


# --------------------------------------------------------------------------
# Value reshaping
# --------------------------------------------------------------------------


def field(obj: Any, name: str) -> Any:
    """Read one field from a mapping or a pynetbox record.

    pynetbox exposes fields as attributes; canned test data is mappings.
    Reading both the same way is what lets every function below be tested
    without a server while running against the real client in production.

    Reads a record's ``__dict__`` rather than using ``getattr``. This is not
    style: pynetbox's ``Record.__getattr__`` calls ``full_details()`` for any
    attribute the record does not already hold, which is an HTTP GET. Since
    ``unwrap`` probes ``value`` before ``name``, a bare ``getattr`` fires one
    request per nested object — thousands of them across a real catalogue,
    against a customer's production NetBox, to learn nothing.

    Args:
        obj: A mapping or a pynetbox record.
        name: The field to read.

    Returns:
        The field's value, or ``None`` when it is absent.
    """
    if isinstance(obj, dict):
        return obj.get(name)
    try:
        return vars(obj).get(name)
    except TypeError:  # objects without __dict__, e.g. slots
        return getattr(obj, name, None)


def unwrap(value: Any) -> Any:
    """Reduce a NetBox value to its library-format equivalent.

    Choice fields carry ``value`` and ``label``; related objects carry a
    ``name``. The library format wants the bare choice value and the related
    object's name, so the first of those that is present wins.

    Note that pynetbox's own ``Record.serialize()`` is not usable here: it
    flattens a related object to its primary key, so a power outlet's
    ``power_port`` would become ``16`` where the library needs ``"Input"``.

    Args:
        value: A raw value from NetBox.

    Returns:
        The unwrapped value, or the input when nothing needs unwrapping.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    for key in ("value", "name", "slug"):
        found = field(value, key)
        if found is not None:
            return found
    return value


def as_number(value: Any) -> Any:
    """Coerce a NetBox decimal-as-string back to a number.

    Args:
        value: A raw value from the API.

    Returns:
        An ``int`` where the value is integral, a ``float`` where it is not,
        and the input unchanged when it is not numeric at all.
    """
    if isinstance(value, bool) or value is None:
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def is_present(value: Any) -> bool:
    """Return True for a value worth writing.

    The library format omits fields rather than carrying nulls or empty
    strings, so an absent NetBox value must not become ``field: null``.
    Booleans and zero are kept: ``is_full_depth: false`` and
    ``u_height: 0`` are both meaningful.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def carry_fields(source: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Copy the named fields out of an API object, cleaned and in order.

    Args:
        source: One object from the API.
        fields: Field names to carry, in output order.

    Returns:
        The cleaned subset, with absent values omitted entirely.
    """
    carried: dict[str, Any] = {}
    for name in fields:
        value = unwrap(field(source, name))
        if name in NUMERIC_FIELDS:
            value = as_number(value)
        if is_present(value):
            carried[name] = value
    return carried


def port_mappings(
    front_ports: list[dict[str, Any]], rear_ports: list[dict[str, Any]]
) -> list[dict]:
    """Resolve front/rear port mappings from primary keys to names.

    NetBox models the mapping as a many-to-many carrying a position on each
    end and referencing the rear port by id. The library format names both
    ports instead, so the rear ports have to be indexed by id first.

    Args:
        front_ports: Raw front-port template objects.
        rear_ports: Raw rear-port template objects.

    Returns:
        The library's ``port-mappings`` entries, ordered by front port then
        position. Empty when nothing is mapped.
    """
    by_id = {field(rear, "id"): field(rear, "name") for rear in rear_ports}
    mappings: list[dict[str, Any]] = []
    for front in front_ports:
        for mapping in field(front, "rear_ports") or []:
            rear_ref = field(mapping, "rear_port")
            rear_name = by_id.get(field(rear_ref, "id") if not isinstance(rear_ref, int) else rear_ref)
            if rear_name is None:
                continue
            mappings.append(
                {
                    "front_port": field(front, "name"),
                    "front_port_position": as_number(field(mapping, "position")),
                    "rear_port": rear_name,
                    "rear_port_position": as_number(field(mapping, "rear_port_position")),
                }
            )
    return mappings


# --------------------------------------------------------------------------
# Document assembly
# --------------------------------------------------------------------------


def build_document(
    source: dict[str, Any],
    components: dict[str, list[dict[str, Any]]],
    *,
    is_module: bool,
) -> tuple[dict[str, Any], list[str]]:
    """Assemble one devicetype-library document.

    Args:
        source: The device-type or module-type object from the API.
        components: Component-template objects, keyed by library list name.
        is_module: Whether this is a module type.

    Returns:
        ``(document, notes)``. ``notes`` names anything the API reported that
        the library format has no field for.
    """
    fields = MODULE_TYPE_FIELDS if is_module else DEVICE_TYPE_FIELDS
    document = carry_fields(source, fields)
    notes: list[str] = []

    allowed = (
        MODULE_COMPONENT_LISTS if is_module else {name for _, name in DEVICE_COMPONENTS}
    )
    for _, list_name in DEVICE_COMPONENTS:
        entries = components.get(list_name) or []
        if not entries:
            continue
        if list_name not in allowed:
            notes.append(f"{list_name} ({len(entries)}) — not valid on a module type")
            continue
        carried = [carry_fields(e, COMPONENT_FIELDS[list_name]) for e in entries]
        document[list_name] = carried
        notes.extend(missing_required(carried, list_name))

    mappings = port_mappings(
        components.get("front-ports") or [], components.get("rear-ports") or []
    )
    if mappings:
        document["port-mappings"] = mappings

    if is_module and field(source, "attributes"):
        notes.append("attributes — NetBox module-type profile data, no library field")
    required = (
        REQUIRED_MODULE_TYPE_FIELDS if is_module else REQUIRED_DEVICE_TYPE_FIELDS
    )
    absent = [f for f in required if f not in document]
    if absent:
        notes.append(
            f"unset in NetBox but required by the library schema: {', '.join(absent)}"
        )
    return document, notes


def missing_required(entries: list[dict[str, Any]], list_name: str) -> list[str]:
    """Report entries missing a field the library schema requires.

    NetBox is the looser of the two: a power port with no type is valid
    there and invalid in the library format. Emitting it anyway is right —
    the data is real — but saying nothing would hand over a file that fails
    the library's own validation for reasons that look like our bug.

    Args:
        entries: The carried component entries.
        list_name: The devicetype-library list they belong to.

    Returns:
        One note per missing field, naming how many entries lack it.
    """
    notes: list[str] = []
    for field in REQUIRED_COMPONENT_FIELDS.get(list_name, ()):
        count = sum(1 for entry in entries if field not in entry)
        if count:
            notes.append(
                f"{list_name}: {count} of {len(entries)} unset {field!r}, "
                "which the library schema requires"
            )
    return notes


def render_document(document: dict[str, Any]) -> str:
    """Render one document as devicetype-library YAML."""
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )
    return f"---\n{body}"


def output_path(
    document: dict[str, Any],
    out_dir: Path,
    is_module: bool,
    taken: set[Path] | None = None,
) -> Path:
    """Return the library's path for a document, avoiding collisions.

    The library lays files out as ``<Manufacturer>/<slug>.yaml``. Module
    types have no slug, so the model stands in, matching how the converter
    identifies them.

    Sanitising a name can collapse two distinct records onto one path.
    NetBox enforces ``(manufacturer, slug)`` and ``(manufacturer, model)``
    uniqueness, but not after the substitutions below: a module type named
    ``EX9200 32XS`` and one named ``EX9200-32XS`` are both legal and both
    want ``EX9200-32XS.yaml``. Passing ``taken`` makes the second one land
    beside the first instead of on top of it.

    Args:
        document: The assembled library document.
        out_dir: Root of the output tree.
        is_module: Whether this is a module type.
        taken: Paths already claimed, updated in place. When ``None`` no
            collision handling is applied.

    Returns:
        The path to write to.
    """
    manufacturer = str(document.get("manufacturer") or "Unknown")
    stem = str(document.get("slug") or document.get("model") or "unnamed")
    safe = _safe(stem.replace(" ", "-"), "unnamed")
    root = out_dir / ("module-types" if is_module else "device-types") / _safe(manufacturer)

    path = root / f"{safe}.yaml"
    if taken is None:
        return path
    suffix = 1
    while path in taken:
        suffix += 1
        path = root / f"{safe}-{suffix}.yaml"
    taken.add(path)
    return path


#: Path segments that would move the write somewhere other than where the
#: layout says. A NetBox manufacturer is free text, so these are reachable.
_RESERVED_SEGMENTS = frozenset({"", ".", ".."})


def _safe(name: str, fallback: str = "Unknown") -> str:
    """Reduce a name to a single, inert path segment.

    ``..`` has to be rejected rather than merely slash-stripped: a
    manufacturer named ``..`` lands the file in the output root instead of
    under ``device-types/``, where it can collide with the module-types
    tree and breaks the layout the converter walks.

    Args:
        name: The raw NetBox name.
        fallback: Used when the name reduces to nothing usable.

    Returns:
        A single path segment safe to join.
    """
    segment = name.replace("/", "-").replace("\\", "-").strip()
    return fallback if segment in _RESERVED_SEGMENTS else segment


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def _only_in_use(objects: list[Any], *, is_module: bool) -> tuple[list[Any], int]:
    """Keep the types that are actually used, and count the undecidable ones.

    A record whose count is *absent* is kept rather than dropped. Treating a
    missing field as zero would silently export nothing against any NetBox
    that does not report the count, which is the same silent-empty-export
    failure a wrong ``--url`` used to cause.

    Args:
        objects: Device or module types from NetBox.
        is_module: Whether these are module types.

    Returns:
        ``(kept, undecidable)``.
    """
    counter = "module_count" if is_module else "device_count"
    kept: list[Any] = []
    undecidable = 0
    for obj in objects:
        count = field(obj, counter)
        if count is None:
            undecidable += 1
            kept.append(obj)
        elif count > 0:
            kept.append(obj)
    return kept, undecidable


def _identity(obj: Any) -> tuple[str, str, str]:
    """A stable sort key for one device or module type.

    Sorts on the name a record competes for, then on its full identity, so
    the ordering does not change when NetBox reorders its results.
    """
    manufacturer = str(unwrap(field(obj, "manufacturer")) or "")
    stem = str(field(obj, "slug") or field(obj, "model") or "")
    return (manufacturer, stem.replace("/", "-").replace(" ", "-"), stem)


def _expected_stem(document: dict[str, Any]) -> str:
    """The file stem a document would get if nothing else had claimed it."""
    stem = str(document.get("slug") or document.get("model") or "unnamed")
    return stem.replace("/", "-").replace(" ", "-")


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    """Split a list into fixed-size chunks."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_components(
    source: Source, ids: list[Any], *, is_module: bool
) -> dict[Any, dict[str, list[Any]]]:
    """Fetch every component template for a set of device or module types.

    NetBox accepts a repeated id filter, so components for many parents come
    back per endpoint rather than per parent — ten calls per batch instead of
    ten per device type.

    Args:
        source: Where to read from.
        ids: Device-type or module-type ids.
        is_module: Whether the ids are module types.

    Returns:
        Components keyed by parent id, then by library list name.
    """
    key = "module_type_id" if is_module else "device_type_id"
    parent = "module_type" if is_module else "device_type"
    grouped: dict[Any, dict[str, list[Any]]] = {i: {} for i in ids}

    for endpoint, list_name in DEVICE_COMPONENTS:
        if is_module and list_name not in MODULE_COMPONENT_LISTS:
            continue
        for batch in chunked(ids, ID_BATCH):
            for item in source.records(endpoint, **{key: batch}):
                owner = field(field(item, parent), "id")
                if owner in grouped:
                    grouped[owner].setdefault(list_name, []).append(item)
    return grouped


def export(
    source: Source,
    out_dir: Path,
    *,
    filters: dict[str, Any],
    in_use: bool,
    include_modules: bool,
) -> tuple[list[Path], list[str]]:
    """Run the export.

    Args:
        source: Where to read from.
        out_dir: Directory to write the library tree into.
        filters: Query filters selecting which types to export.
        in_use: Restrict device types to those with at least one device.
        include_modules: Also export module types.

    Returns:
        ``(written_paths, notes)``.
    """
    written: list[Path] = []
    notes: list[str] = []
    taken: set[Path] = set()

    for is_module, endpoint in ((False, DEVICE_TYPES), (True, MODULE_TYPES)):
        if is_module and not include_modules:
            continue
        # A module type has no slug, and NetBox's strict filtering rejects an
        # unknown filter with a 400 rather than ignoring it — so passing the
        # device-type slug filter here would abort the whole export.
        applicable = {k: v for k, v in filters.items() if not (is_module and k == "slug")}
        objects = list(source.records(endpoint, **applicable))
        if in_use:
            objects, unknown = _only_in_use(objects, is_module=is_module)
            if unknown:
                notes.append(
                    f"{endpoint}: {unknown} record(s) kept because this NetBox did not "
                    "report a usage count — --in-use could not judge them"
                )
        if not objects:
            continue

        ids = [field(o, "id") for o in objects if field(o, "id") is not None]
        components = fetch_components(source, ids, is_module=is_module)

        # Sort before writing so collision suffixes are deterministic. Two
        # records whose names collide only after sanitising are assigned
        # `-2` by arrival order otherwise, which swaps their contents between
        # runs whenever NetBox returns them in a different order — a spurious
        # diff, and unstable identities for anything built on the filenames.
        objects.sort(key=_identity)

        for obj in objects:
            owned = components.get(field(obj, "id")) or {}
            document, doc_notes = build_document(obj, owned, is_module=is_module)
            path = output_path(document, out_dir, is_module, taken)
            if path.stem != _expected_stem(document):
                doc_notes.append(
                    f"file name collided after sanitising; written as {path.name} "
                    "so it does not overwrite the record it collided with"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_document(document), encoding="utf-8")
            written.append(path)
            notes.extend(f"{document.get('model', '?')}: {note}" for note in doc_notes)

    for endpoint in sorted(getattr(source, "missing_endpoints", ())):
        notes.append(f"{endpoint} — endpoint absent from this NetBox, list not exported")
    return written, notes


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="netbox_export_device_types.py",
        description="Export device and module types from a live NetBox into "
        "devicetype-library YAML, ready for netbox_to_infrahub_templates.py.",
    )
    parser.add_argument("--url", required=True, help="Base URL of the NetBox instance.")
    parser.add_argument(
        "--token",
        default=os.environ.get("NETBOX_TOKEN", ""),
        help="API token. Defaults to $NETBOX_TOKEN.",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="Directory to write into."
    )
    parser.add_argument(
        "--manufacturer",
        action="append",
        default=[],
        metavar="SLUG",
        help="Restrict to a manufacturer slug. Repeatable.",
    )
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        help="Restrict to a device-type slug. Repeatable.",
    )
    parser.add_argument(
        "--in-use",
        action="store_true",
        help="Only types that are in use — device types with at least one device, and "
        "module types with at least one module. Usually what you want.",
    )
    parser.add_argument(
        "--module-types", action="store_true", help="Also export module types."
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="Per-request timeout."
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS verification (self-signed certs).",
    )
    return parser


def selection_filters(args: argparse.Namespace) -> dict[str, Any]:
    """Turn CLI selection arguments into pynetbox filters.

    A list value becomes a repeated query parameter, which is how NetBox
    expresses "any of these".
    """
    filters: dict[str, Any] = {}
    if args.manufacturer:
        filters["manufacturer"] = args.manufacturer
    if args.slug:
        filters["slug"] = args.slug
    return filters


def main(argv: list[str] | None = None) -> int:
    """Run the exporter.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    try:
        if not args.token:
            raise ExportError("No API token. Pass --token or set NETBOX_TOKEN.")
        if urllib.parse.urlparse(args.url).scheme not in ("http", "https"):
            raise ExportError(f"--url must be an http(s) URL, got {args.url!r}")

        source = NetBoxSource(
            args.url, args.token, verify=not args.insecure, timeout=args.timeout
        )
        written, notes = export(
            source,
            args.output_dir,
            filters=selection_filters(args),
            in_use=args.in_use,
            include_modules=args.module_types,
        )
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Print the notes before deciding the exit code: an empty export is
    # exactly when the reader most needs to know what was skipped and why.
    if notes:
        print("\nNot carried into the library format:", file=sys.stderr)
        for note in notes:
            print(f"  - {note}", file=sys.stderr)

    if not written:
        print("\nNo device types matched the given filters.", file=sys.stderr)
        return 2

    for path in written:
        print(path)
    print(f"\n{len(written)} file(s) written to {args.output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
