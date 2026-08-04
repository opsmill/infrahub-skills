"""Materialise module-declared ports as real device interfaces.

NetBox module types declare the ports a module provides, with a ``{module}``
token that NetBox substitutes with the bay position when the module is
installed. Those declarations import into Infrahub as ``DeviceModulePort``
objects parented by the module (schema-library ``extensions/module_port``).
They are declarations only: the token is still literal, and they are not
``DcimInterface`` objects, so they cannot be cabled, addressed, or queried as
device interfaces.

They deliberately are not interfaces. ``DcimInterface.device`` is a mandatory
``Parent``, and Infrahub requires a relationship used in a uniqueness
constraint to be mandatory -- every interface kind is keyed
``[device, name__value]`` with a ``device__name__value`` human_friendly_id.
Making ``device`` optional so an interface could hang off a module instead
fails schema validation outright::

    DcimConsoleInterface.uniqueness_constraints: cannot use device
    relationship, relationship must be mandatory. (`device`)

So the port stays a declaration on the module, and this generator creates the
corresponding real interface on the device. It is a generator rather than an
object template because ``{module}`` resolves to a bay position that is only
known once the module is installed, and a template is not bound to a bay.

What it does, per device
------------------------
For each installed module (``device.modules``), resolve the bay position, then
for each of the module's ports substitute the token and create the device-side
object routed by ``port.category``:

===========  ==============================================================
``category`` Outcome
===========  ==============================================================
interface    ``InterfacePhysical`` on ``device.interfaces``; ``role`` set to
             ``management`` when ``mgmt_only`` is true
console      A console interface kind, **only if the loaded schema has one**.
             Stock schema-library does not, so this normally skips with a
             logged reason. See ``CONSOLE_INTERFACE_KIND``.
power        No home in the stock schema. Skipped with a logged reason --
front        no mapping is invented for them.
rear
===========  ==============================================================

Routing is by category *and* schema availability: every candidate kind is
probed with ``client.schema.get`` before use, so a missing kind is a logged
skip rather than a failed run.

Where ``port_type`` goes: nowhere, by default
---------------------------------------------
``DeviceModulePort.port_type`` holds a NetBox slug (``1000base-t``, ``rj-45``,
``iec-60320-c14``). Stock ``InterfacePhysical`` has **no media-type
attribute** -- its own attribute list is empty, and the ``DcimInterface``
generic it inherits declares only ``name``, ``description``, ``mtu``,
``status``, and ``role``. So ``port_type`` is **dropped**, and the drop is
counted and reported rather than hidden.

If your schema does have somewhere for it, set ``PORT_TYPE_ATTRIBUTE`` to that
attribute's name. It is validated against the target kind's real attribute list
at run time and disabled with a warning if absent, so a wrong guess degrades to
the default rather than failing every create. No attribute name is guessed here.

Idempotency and provenance
--------------------------
``run()`` wraps ``generate()`` in a tracking context with
``delete_unused_nodes=True``, and every ``save()`` uses ``allow_upsert=True``,
which is the mechanism the skill prescribes -- see
``skills/infrahub-managing-generators/rules/tracking-idempotent.md``. Re-running
re-creates the same names and updates in place.

Tracking alone cannot tell "an interface this generator owns" from "an
interface someone else created at the same name", and the two need opposite
handling: the first is upserted, the second must be left alone. So every
interface this generator writes carries a provenance marker in
``description``::

    [module-port] module JPE12345678 bay 3

A resolved name that collides with an interface **without** that marker is
skipped and reported -- upserting it would silently take ownership of somebody
else's interface, and the next run's cleanup would then delete it.

The flip side of ``delete_unused_nodes=True`` is worth stating plainly: an
interface this generator created on a previous run and does *not* recreate on
this one gets **deleted**. That is correct desired-state behaviour when a module
is removed, and it is also what happens when a bay position becomes null. The
skip log is where that shows up.

Registration
------------
::

    queries:
      - name: module_ports_for_device
        file_path: queries/module_ports_for_device.gql

    generator_definitions:
      - name: materialize_module_ports
        file_path: generators/materialize_module_ports.py
        query: module_ports_for_device
        targets: devices_with_modules
        class_name: ModulePortMaterializer
        parameters:
          device_name: name__value

``targets`` must be a ``CoreGeneratorGroup``; a ``CoreStandardGroup`` of the
same name parses but never triggers. See
``skills/infrahub-managing-generators/rules/registration-config.md``.

Testing
-------
Unit tests for the planning logic:
``tests/scripts/test_materialize_module_ports.py``. They do not cover SDK call
shape -- run it end to end against a live instance before declaring it done,
per ``skills/infrahub-managing-generators/rules/testing-integration.md``::

    infrahubctl generator list
    infrahubctl generator run materialize_module_ports --branch <branch>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from infrahub_sdk.exceptions import SchemaNotFoundError
from infrahub_sdk.generator import InfrahubGenerator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: The token NetBox substitutes with the bay position.
POSITION_TOKEN = "{module}"

#: Prefix written into every created interface's ``description``, so a later
#: run can tell its own objects from foreign ones at the same name.
PROVENANCE_PREFIX = "[module-port]"

#: Category used when a port declares none. Mirrors the schema default on
#: ``DeviceModulePort.category``.
DEFAULT_CATEGORY = "interface"

#: Kind created for a network interface port.
INTERFACE_KIND = "InterfacePhysical"

#: Candidate kind for a console port. Stock schema-library has no console
#: interface kind; some schemas add one inheriting ``DcimInterface``. Probed
#: before use, so leaving this set is safe -- an absent kind is a logged skip.
CONSOLE_INTERFACE_KIND = "DcimConsoleInterface"

#: ``category`` -> kind to create. ``None`` means the stock schema has no home
#: for this category. Do not invent one: a power inlet is not an interface, and
#: front/rear ports are pass-through patch positions that need their own node.
CATEGORY_TARGETS: dict[str, str | None] = {
    "interface": INTERFACE_KIND,
    "console": CONSOLE_INTERFACE_KIND,
    "power": None,
    "front": None,
    "rear": None,
}

#: ``role`` for a management-only interface port. ``management`` is a declared
#: choice on ``DcimInterface.role`` in schema-library.
MGMT_ROLE: str | None = "management"

#: ``role`` for a console port, or ``None`` to leave it unset.
#:
#: Deliberately ``None``. ``role`` is a ``Dropdown`` and Infrahub rejects an
#: undeclared value, and schema-library's choices are ``lag``, ``core``,
#: ``cust``, ``access``, ``management``, ``peering``, ``upstream`` -- there is
#: no ``console``. A schema that adds a console interface kind may or may not
#: also add the choice, so set this only after checking yours.
CONSOLE_ROLE: str | None = None

#: Attribute receiving ``port_type``, or ``None`` to drop it (the default; see
#: the module docstring). Validated against the target kind at run time.
PORT_TYPE_ATTRIBUTE: str | None = None

# ---------------------------------------------------------------------------
# Skip reasons
# ---------------------------------------------------------------------------

REASON_UNNAMED = "port has no name"
REASON_UNKNOWN_CATEGORY = "unrecognised category"
REASON_NO_TARGET_KIND = "no target kind for this category"
REASON_KIND_NOT_IN_SCHEMA = "target kind not in the loaded schema"
REASON_POSITION_UNRESOLVED = "bay position unknown, and the name needs it"
REASON_DUPLICATE_IN_RUN = "another module already claimed this name this run"
REASON_NAME_TAKEN = "an interface not created by this generator holds this name"

#: How a position was resolved, for reporting.
POSITION_FROM_BAY = "module_bay.position"
POSITION_FROM_SLOT = "concrete-kind slot"
POSITION_BAY_WITHOUT_POSITION = "module_bay set but position is null"
POSITION_NO_BAY = "module has no module_bay"


# ---------------------------------------------------------------------------
# GraphQL response helpers
# ---------------------------------------------------------------------------


def scalar(wrapper: Any) -> Any:
    """Return the ``value`` inside a GraphQL attribute wrapper.

    Args:
        wrapper: A ``{"value": ...}`` mapping, or anything else.

    Returns:
        The wrapped value, or ``None`` when the wrapper is absent or malformed.
    """
    if isinstance(wrapper, dict):
        return wrapper.get("value")
    return None


def peer(wrapper: Any) -> dict | None:
    """Return the node behind a ``cardinality: one`` relationship.

    Args:
        wrapper: A ``{"node": {...}}`` mapping, or anything else.

    Returns:
        The peer node, or ``None`` when the relationship is unset. An unset
        single relationship arrives as ``None`` or as ``{"node": None}``.
    """
    if isinstance(wrapper, dict):
        node = wrapper.get("node")
        if isinstance(node, dict):
            return node
    return None


def peers(wrapper: Any) -> list[dict]:
    """Return the nodes behind a ``cardinality: many`` relationship.

    Args:
        wrapper: An ``{"edges": [{"node": {...}}]}`` mapping, or anything else.

    Returns:
        The peer nodes, empty when the relationship is unset or empty.
    """
    if not isinstance(wrapper, dict):
        return []
    edges = wrapper.get("edges")
    if not isinstance(edges, list):
        return []
    return [edge["node"] for edge in edges if isinstance(edge, dict) and isinstance(edge.get("node"), dict)]


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedInterface:
    """One interface to create, already resolved and collision-checked."""

    kind: str
    name: str
    device_id: str
    device_name: str
    description: str
    role: str | None
    port_type: str | None
    port_type_attribute: str | None
    module_serial: str
    declared_name: str
    position: str | None


@dataclass(frozen=True)
class SkippedPort:
    """One port that produced no interface, and why."""

    module_serial: str
    port_name: str
    category: str
    reason: str
    detail: str = ""

    def render(self) -> str:
        """Return a single-line, log-ready description of the skip."""
        suffix = f" ({self.detail})" if self.detail else ""
        return (
            f"module {self.module_serial}: {self.category} port "
            f"'{self.port_name}' skipped -- {self.reason}{suffix}"
        )


@dataclass
class DevicePlan:
    """Everything this generator intends to do to one device."""

    device_name: str
    device_id: str
    creates: list[PlannedInterface] = field(default_factory=list)
    skips: list[SkippedPort] = field(default_factory=list)
    dropped_port_types: int = 0

    def summary(self) -> str:
        """Return a one-line summary naming the skip reasons and their counts."""
        parts = [f"{len(self.creates)} interface(s) planned", f"{len(self.skips)} port(s) skipped"]
        if self.skips:
            counts: dict[str, int] = {}
            for skip in self.skips:
                counts[skip.reason] = counts.get(skip.reason, 0) + 1
            detail = ", ".join(f"{reason} x{count}" for reason, count in sorted(counts.items()))
            parts.append(f"[{detail}]")
        if self.dropped_port_types:
            parts.append(f"{self.dropped_port_types} port_type value(s) dropped")
        return f"{self.device_name}: " + "; ".join(parts)


def is_ours(description: Any) -> bool:
    """Return True if a description carries this generator's provenance marker."""
    return str(description or "").startswith(PROVENANCE_PREFIX)


def provenance(module_serial: str, position: str | None) -> str:
    """Build the provenance description stamped onto a created interface.

    Args:
        module_serial: Serial number of the module that declared the port.
        position: Resolved bay position, or ``None`` when the name needed none.

    Returns:
        A description string beginning with :data:`PROVENANCE_PREFIX`.
    """
    text = f"{PROVENANCE_PREFIX} module {module_serial}"
    if position is not None:
        text += f" bay {position}"
    return text


def resolve_position(module: dict) -> tuple[str | None, str]:
    """Resolve the bay position of an installed module.

    Prefers ``module_bay.position``, the canonical free-form position. Falls
    back to a concrete-kind ``slot`` value when the query enables that inline
    fragment and the bay gives nothing usable.

    Args:
        module: A module node from the GraphQL response.

    Returns:
        ``(position, source)``. ``position`` is ``None`` when nothing usable
        was found; ``source`` always explains which branch was taken, so the
        caller can report *why* a position is missing.
    """
    bay = peer(module.get("module_bay"))

    if bay is not None:
        position = scalar(bay.get("position"))
        if position is not None and str(position).strip():
            return str(position), POSITION_FROM_BAY

    # Only present when the query's concrete-kind fragment is enabled.
    slot = scalar(module.get("slot"))
    if slot is not None and str(slot).strip():
        return str(slot), POSITION_FROM_SLOT

    if bay is not None:
        return None, POSITION_BAY_WITHOUT_POSITION
    return None, POSITION_NO_BAY


def resolve_name(declared_name: str, position: str | None) -> str | None:
    """Substitute the position token in a declared port name.

    A name with no token is valid and used as-is -- not every module type
    tokenises its ports (``EX-PWR-320-AC`` declares a bare ``PSU``).

    Args:
        declared_name: Port name as declared by the module type.
        position: Resolved bay position, or ``None`` if unknown.

    Returns:
        The resolved name, or ``None`` when the name needs a position that is
        not available.
    """
    if POSITION_TOKEN not in declared_name:
        return declared_name
    if position is None:
        return None
    return declared_name.replace(POSITION_TOKEN, position)


def existing_interfaces(device: dict) -> dict[str, str]:
    """Index a device's current interfaces by name.

    Args:
        device: A device node from the GraphQL response.

    Returns:
        Mapping of interface name to its description (empty string when unset).
    """
    index: dict[str, str] = {}
    for interface in peers(device.get("interfaces")):
        name = scalar(interface.get("name"))
        if name:
            index[str(name)] = str(scalar(interface.get("description")) or "")
    return index


def plan_device(
    device: dict,
    available_kinds: set[str],
    port_type_attributes: dict[str, str] | None = None,
) -> DevicePlan:
    """Compute what to create on one device, and what to skip.

    Pure: no SDK calls, no I/O. Everything the generator decides lives here so
    it can be unit-tested against a recorded GraphQL response.

    Args:
        device: A device node from the GraphQL response.
        available_kinds: Kinds confirmed present in the loaded schema.
        port_type_attributes: Per-kind attribute that should receive
            ``port_type``. Absent kinds drop the value.

    Returns:
        The :class:`DevicePlan` for this device.
    """
    port_type_attributes = port_type_attributes or {}
    plan = DevicePlan(
        device_name=str(scalar(device.get("name")) or ""),
        device_id=str(device.get("id") or ""),
    )
    existing = existing_interfaces(device)
    claimed: dict[str, str] = {}

    for module in peers(device.get("modules")):
        module_serial = str(scalar(module.get("serial_number")) or "<no serial>")
        position, position_source = resolve_position(module)

        for port in peers(module.get("ports")):
            outcome = _decide_port(
                port=port,
                module_serial=module_serial,
                position=position,
                position_source=position_source,
                plan=plan,
                available_kinds=available_kinds,
                port_type_attributes=port_type_attributes,
                existing=existing,
                claimed=claimed,
            )
            if isinstance(outcome, SkippedPort):
                plan.skips.append(outcome)
                continue
            claimed[outcome.name] = module_serial
            plan.creates.append(outcome)

    return plan


def _decide_port(
    *,
    port: dict,
    module_serial: str,
    position: str | None,
    position_source: str,
    plan: DevicePlan,
    available_kinds: set[str],
    port_type_attributes: dict[str, str],
    existing: dict[str, str],
    claimed: dict[str, str],
) -> PlannedInterface | SkippedPort:
    """Route one declared port to an interface to create, or to a skip.

    The order of checks is the order in which a reason stops being useful:
    an unmapped category is unconditional, so it is reported before anything
    about positions or collisions.
    """
    declared_name = scalar(port.get("name"))
    category = str(scalar(port.get("category")) or DEFAULT_CATEGORY)

    if not declared_name:
        return SkippedPort(module_serial, "<unnamed>", category, REASON_UNNAMED)
    declared_name = str(declared_name)

    if category not in CATEGORY_TARGETS:
        return SkippedPort(
            module_serial,
            declared_name,
            category,
            REASON_UNKNOWN_CATEGORY,
            f"known categories: {', '.join(sorted(CATEGORY_TARGETS))}",
        )

    kind = CATEGORY_TARGETS[category]
    if kind is None:
        return SkippedPort(
            module_serial, declared_name, category, REASON_NO_TARGET_KIND, _port_detail(port)
        )

    if kind not in available_kinds:
        return SkippedPort(
            module_serial,
            declared_name,
            category,
            REASON_KIND_NOT_IN_SCHEMA,
            f"{kind} is not defined; add it or leave these ports as declarations",
        )

    resolved = resolve_name(declared_name, position)
    if resolved is None:
        return SkippedPort(
            module_serial, declared_name, category, REASON_POSITION_UNRESOLVED, position_source
        )

    if resolved in claimed:
        return SkippedPort(
            module_serial,
            declared_name,
            category,
            REASON_DUPLICATE_IN_RUN,
            f"'{resolved}' already claimed by module {claimed[resolved]}",
        )

    if resolved in existing and not is_ours(existing[resolved]):
        return SkippedPort(
            module_serial,
            declared_name,
            category,
            REASON_NAME_TAKEN,
            f"'{resolved}' exists on {plan.device_name} without the provenance marker",
        )

    port_type = scalar(port.get("port_type"))
    target_attribute = port_type_attributes.get(kind)
    if port_type and not target_attribute:
        plan.dropped_port_types += 1

    role = MGMT_ROLE if (category == "interface" and scalar(port.get("mgmt_only"))) else None
    if category == "console":
        role = CONSOLE_ROLE

    return PlannedInterface(
        kind=kind,
        name=resolved,
        device_id=plan.device_id,
        device_name=plan.device_name,
        description=provenance(module_serial, position if POSITION_TOKEN in declared_name else None),
        role=role,
        port_type=str(port_type) if port_type and target_attribute else None,
        port_type_attribute=target_attribute,
        module_serial=module_serial,
        declared_name=declared_name,
        position=position,
    )


def _port_detail(port: dict) -> str:
    """Summarise a port's own fields, so an unmapped skip stays actionable."""
    bits = []
    port_type = scalar(port.get("port_type"))
    if port_type:
        bits.append(f"type {port_type}")
    draw = scalar(port.get("maximum_draw"))
    if draw is not None:
        bits.append(f"{draw} W")
    return ", ".join(bits)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class ModulePortMaterializer(InfrahubGenerator):
    """Create device interfaces from the ports declared by installed modules."""

    async def generate(self, data: dict) -> None:
        """Create one interface per resolvable module port on each target device.

        Args:
            data: Result of the ``module_ports_for_device`` query.
        """
        devices = peers(data.get("DcimDevice"))
        if not devices:
            self.logger.warning(
                "No device matched the query; nothing to materialise. Check the "
                "generator's target group and the device_name parameter."
            )
            return

        available_kinds, port_type_attributes = await self._probe_target_kinds()
        if not available_kinds:
            self.logger.warning(
                "None of the candidate interface kinds (%s) exist in the schema on "
                "branch %s; every port will be skipped.",
                ", ".join(sorted(kind for kind in CATEGORY_TARGETS.values() if kind)),
                self.branch_name,
            )

        for device in devices:
            plan = plan_device(
                device,
                available_kinds=available_kinds,
                port_type_attributes=port_type_attributes,
            )

            for planned in plan.creates:
                await self._create_interface(planned)

            # Every skip is logged individually. A silent skip reads as
            # "nothing to do", which is the failure mode this generator is
            # most likely to be blamed for.
            for skip in plan.skips:
                self.logger.info(skip.render())

            self.logger.info(plan.summary())

    async def _create_interface(self, planned: PlannedInterface) -> None:
        """Upsert one interface on its device.

        ``device`` is passed as ``{"id": ...}`` because the query already
        returned the device's UUID -- no HFID lookup round trip needed. The
        device side of the Component/Parent pair is wired by setting the Parent
        here, so there is no ``device.interfaces.add()`` to make (and were there
        one, ``RelationshipManager.add`` takes a single peer per call).

        Args:
            planned: The resolved interface to create or update.
        """
        payload: dict[str, Any] = {
            "name": planned.name,
            "device": {"id": planned.device_id},
            "description": planned.description,
        }
        if planned.role is not None:
            payload["role"] = planned.role
        # The attribute name was resolved against the target kind's real
        # attribute list when the plan was built, so it is known to exist.
        if planned.port_type is not None and planned.port_type_attribute:
            payload[planned.port_type_attribute] = planned.port_type

        interface = await self.client.create(kind=planned.kind, data=payload)
        # allow_upsert is what makes the re-run idempotent; without it the
        # second run raises on the first existing interface and abandons the
        # rest of the device.
        await interface.save(allow_upsert=True)
        self.logger.info(
            "%s: %s '%s' from module %s port '%s'",
            planned.device_name,
            planned.kind,
            planned.name,
            planned.module_serial,
            planned.declared_name,
        )

    async def _probe_target_kinds(self) -> tuple[set[str], dict[str, str]]:
        """Find which candidate kinds the loaded schema actually defines.

        Routing by category alone would assume a console interface kind exists.
        Probing instead turns a missing kind into a reported skip.

        Also resolves :data:`PORT_TYPE_ATTRIBUTE` against each kind's real
        attribute list, so a name the schema does not have is dropped with a
        warning rather than failing every create.

        Returns:
            ``(available_kinds, port_type_attributes)``.
        """
        available: set[str] = set()
        port_type_attributes: dict[str, str] = {}

        for kind in sorted({kind for kind in CATEGORY_TARGETS.values() if kind}):
            try:
                node_schema = await self.client.schema.get(kind=kind, branch=self.branch_name)
            except SchemaNotFoundError:
                self.logger.info(
                    "Kind %s is not in the schema on branch %s; ports routed to it will be skipped.",
                    kind,
                    self.branch_name,
                )
                continue

            available.add(kind)

            if not PORT_TYPE_ATTRIBUTE:
                continue
            attribute_names = {attribute.name for attribute in node_schema.attributes}
            if PORT_TYPE_ATTRIBUTE in attribute_names:
                port_type_attributes[kind] = PORT_TYPE_ATTRIBUTE
            else:
                self.logger.warning(
                    "PORT_TYPE_ATTRIBUTE '%s' is not an attribute of %s; port_type will be "
                    "dropped for that kind. Set it to one of: %s",
                    PORT_TYPE_ATTRIBUTE,
                    kind,
                    ", ".join(sorted(attribute_names)),
                )

        return available, port_type_attributes
