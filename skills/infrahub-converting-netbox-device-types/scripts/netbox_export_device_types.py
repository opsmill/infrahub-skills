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

Why the standard library rather than pynetbox
---------------------------------------------
pynetbox is the official client and would handle pagination and auth for us.
This script deliberately does not use it: the skill's scripts ship as
reference material to be copied into a customer's repo and run, so an import
that works with nothing but PyYAML installed is worth more here than the
convenience. The HTTP surface used is one paginated ``GET``.

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
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# NetBox API constants
# --------------------------------------------------------------------------

DEVICE_TYPES = "dcim/device-types"
MODULE_TYPES = "dcim/module-types"

#: NetBox component-template endpoints, paired with the devicetype-library
#: list each one becomes. Order matches the library's own field order so the
#: emitted files read like the published ones.
DEVICE_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("dcim/console-port-templates", "console-ports"),
    ("dcim/console-server-port-templates", "console-server-ports"),
    ("dcim/power-port-templates", "power-ports"),
    ("dcim/power-outlet-templates", "power-outlets"),
    ("dcim/interface-templates", "interfaces"),
    ("dcim/front-port-templates", "front-ports"),
    ("dcim/rear-port-templates", "rear-ports"),
    ("dcim/module-bay-templates", "module-bays"),
    ("dcim/device-bay-templates", "device-bays"),
    ("dcim/inventory-item-templates", "inventory-items"),
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

#: Fields that are numeric in the library format. NetBox may serialize a
#: DecimalField as a string, which YAML would then quote.
NUMERIC_FIELDS = frozenset(
    {"u_height", "weight", "maximum_draw", "allocated_draw", "positions"}
)

#: How many object ids to request per component-template call. NetBox accepts
#: a repeated ``device_type_id``, so components for many device types come
#: back in one round trip; the cap keeps the URL within normal server limits.
ID_BATCH = 50

DEFAULT_PAGE_SIZE = 250


class ExportError(Exception):
    """Raised when the export cannot proceed."""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

#: A callable taking (endpoint, params) and returning one decoded API page.
Fetcher = Callable[[str, list[tuple[str, Any]]], dict[str, Any]]


def build_fetcher(url: str, token: str, timeout: float, verify: bool) -> Fetcher:
    """Return a fetcher bound to one NetBox instance.

    Injecting the fetcher is what lets the reshaping logic be tested without
    a server: every function below takes the callable rather than reaching
    for the network itself.

    Args:
        url: Base URL of the NetBox instance.
        token: API token, sent as a ``Token`` authorization header.
        timeout: Per-request timeout in seconds.
        verify: Whether to verify TLS certificates.

    Returns:
        A callable taking an endpoint and query parameters, returning the
        decoded JSON page.
    """
    base = url.rstrip("/")
    context = None if verify else ssl._create_unverified_context()  # noqa: S323

    def fetch(endpoint: str, params: list[tuple[str, Any]]) -> dict[str, Any]:
        target = f"{base}/api/{endpoint}/"
        if params:
            target = f"{target}?{urllib.parse.urlencode(params, doseq=True)}"
        request = urllib.request.Request(  # noqa: S310 - scheme validated in main
            target,
            headers={
                "Authorization": f"Token {token}",
                "Accept": "application/json",
                "User-Agent": "infrahub-skills-netbox-export/1.0",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout, context=context
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ExportError(_http_message(exc, target)) from exc
        except urllib.error.URLError as exc:
            raise ExportError(f"Cannot reach {base}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ExportError(f"{target} did not return JSON: {exc}") from exc

    return fetch


def _http_message(exc: urllib.error.HTTPError, target: str) -> str:
    """Turn an HTTP error into something a reader can act on."""
    if exc.code in (401, 403):
        return (
            f"NetBox rejected the token ({exc.code}). Check --token / NETBOX_TOKEN, "
            "and that the token has read access to dcim."
        )
    if exc.code == 404:
        return f"{target} not found — is --url the base URL, without /api?"
    return f"{target} returned HTTP {exc.code} {exc.reason}"


def paginate(
    fetch: Fetcher, endpoint: str, params: list[tuple[str, Any]]
) -> list[dict[str, Any]]:
    """Return every result across a paginated endpoint.

    Args:
        fetch: The fetcher to use.
        endpoint: API endpoint, e.g. ``dcim/device-types``.
        params: Query parameters, excluding pagination.

    Returns:
        Every object the endpoint yields for those parameters.
    """
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = fetch(
            endpoint, [*params, ("limit", DEFAULT_PAGE_SIZE), ("offset", offset)]
        )
        batch = page.get("results")
        if not isinstance(batch, list):
            raise ExportError(
                f"{endpoint} returned no 'results' list; is this a NetBox API?"
            )
        results.extend(item for item in batch if isinstance(item, dict))
        if not page.get("next"):
            return results
        offset += DEFAULT_PAGE_SIZE


# --------------------------------------------------------------------------
# Value reshaping
# --------------------------------------------------------------------------


def unwrap(value: Any) -> Any:
    """Reduce a NetBox API value to its library-format equivalent.

    Choice fields arrive as ``{"value": ..., "label": ...}`` and related
    objects as nested documents; the library format wants the bare value and
    the related object's name.

    Args:
        value: A raw value from the API.

    Returns:
        The unwrapped value, or the input when nothing needs unwrapping.
    """
    if isinstance(value, dict):
        for key in ("value", "name", "slug"):
            if key in value:
                return value[key]
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
    for field in fields:
        value = unwrap(source.get(field))
        if field in NUMERIC_FIELDS:
            value = as_number(value)
        if is_present(value):
            carried[field] = value
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
    by_id = {rear.get("id"): rear.get("name") for rear in rear_ports}
    mappings: list[dict[str, Any]] = []
    for front in front_ports:
        for mapping in front.get("rear_ports") or []:
            if not isinstance(mapping, dict):
                continue
            rear_name = by_id.get(unwrap(mapping.get("rear_port")))
            if rear_name is None:
                continue
            mappings.append(
                {
                    "front_port": front.get("name"),
                    "front_port_position": as_number(mapping.get("position")),
                    "rear_port": rear_name,
                    "rear_port_position": as_number(mapping.get("rear_port_position")),
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

    if is_module and source.get("attributes"):
        notes.append("attributes — NetBox module-type profile data, no library field")
    if not is_module:
        absent = [f for f in REQUIRED_DEVICE_TYPE_FIELDS if f not in document]
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


def output_path(document: dict[str, Any], out_dir: Path, is_module: bool) -> Path:
    """Return the library's path for a document.

    The library lays files out as ``<Manufacturer>/<slug>.yaml``. Module
    types have no slug, so the model stands in, matching how the converter
    identifies them.
    """
    manufacturer = str(document.get("manufacturer") or "Unknown")
    stem = str(document.get("slug") or document.get("model") or "unnamed")
    safe = stem.replace("/", "-").replace(" ", "-")
    root = out_dir / ("module-types" if is_module else "device-types")
    return root / manufacturer.replace("/", "-") / f"{safe}.yaml"


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    """Split a list into fixed-size chunks."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_components(
    fetch: Fetcher, ids: list[int], *, is_module: bool
) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """Fetch every component template for a set of device or module types.

    NetBox accepts a repeated id filter, so components for many parents come
    back per endpoint rather than per parent — ten requests per batch instead
    of ten per device type.

    Args:
        fetch: The fetcher to use.
        ids: Device-type or module-type ids.
        is_module: Whether the ids are module types.

    Returns:
        Component objects keyed by parent id, then by library list name.
    """
    key = "module_type_id" if is_module else "device_type_id"
    parent = "module_type" if is_module else "device_type"
    grouped: dict[Any, dict[str, list[dict[str, Any]]]] = {i: {} for i in ids}

    for endpoint, list_name in DEVICE_COMPONENTS:
        if is_module and list_name not in MODULE_COMPONENT_LISTS:
            continue
        for batch in chunked(ids, ID_BATCH):
            for item in paginate(fetch, endpoint, [(key, i) for i in batch]):
                owner = unwrap_id(item.get(parent))
                if owner in grouped:
                    grouped[owner].setdefault(list_name, []).append(item)
    return grouped


def unwrap_id(value: Any) -> Any:
    """Return the id of a nested related object, or the value itself."""
    if isinstance(value, dict):
        return value.get("id")
    return value


def export(
    fetch: Fetcher,
    out_dir: Path,
    *,
    filters: list[tuple[str, Any]],
    in_use: bool,
    include_modules: bool,
) -> tuple[list[Path], list[str]]:
    """Run the export.

    Args:
        fetch: The fetcher to use.
        out_dir: Directory to write the library tree into.
        filters: Query parameters selecting which types to export.
        in_use: Restrict device types to those with at least one device.
        include_modules: Also export module types.

    Returns:
        ``(written_paths, notes)``.
    """
    written: list[Path] = []
    notes: list[str] = []

    for is_module, endpoint in ((False, DEVICE_TYPES), (True, MODULE_TYPES)):
        if is_module and not include_modules:
            continue
        objects = paginate(fetch, endpoint, filters)
        if in_use and not is_module:
            objects = [o for o in objects if (o.get("device_count") or 0) > 0]
        if not objects:
            continue

        ids = [o["id"] for o in objects if o.get("id") is not None]
        components = fetch_components(fetch, ids, is_module=is_module)

        for obj in objects:
            owned = components.get(obj.get("id")) or {}
            document, doc_notes = build_document(obj, owned, is_module=is_module)
            path = output_path(document, out_dir, is_module)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_document(document), encoding="utf-8")
            written.append(path)
            notes.extend(f"{document.get('model', '?')}: {note}" for note in doc_notes)

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
        help="Only device types with at least one device, which is usually what you want.",
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


def selection_filters(args: argparse.Namespace) -> list[tuple[str, Any]]:
    """Turn CLI selection arguments into API query parameters."""
    return [
        *[("manufacturer", value) for value in args.manufacturer],
        *[("slug", value) for value in args.slug],
    ]


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

        fetch = build_fetcher(args.url, args.token, args.timeout, not args.insecure)
        written, notes = export(
            fetch,
            args.output_dir,
            filters=selection_filters(args),
            in_use=args.in_use,
            include_modules=args.module_types,
        )
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not written:
        print("No device types matched the given filters.", file=sys.stderr)
        return 2

    for path in written:
        print(path)
    print(f"\n{len(written)} file(s) written to {args.output_dir}", file=sys.stderr)
    if notes:
        print("\nNot carried into the library format:", file=sys.stderr)
        for note in notes:
            print(f"  - {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
