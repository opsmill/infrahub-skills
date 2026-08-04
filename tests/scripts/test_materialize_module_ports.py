"""Tests for the module-port materialising generator.

Covers token substitution, bay-position resolution and its fallbacks,
category routing against schema availability, the unresolvable cases, foreign
name collisions, idempotency on re-run, multi-bay isolation, and the SDK
payload shape the generator writes.

Port fixtures are the real published NetBox module types named in the
devicetype-library, transcribed into the GraphQL response shape the generator
receives:

- ``DCS-7500-SUP2`` — 2 mgmt interfaces plus 1 console port
- ``DCS-7500R-36CQ`` — 36 tokenised interfaces
- ``EX-PWR-320-AC`` — 1 power port, 320 W
- ``DCS-7508R-FM`` — no ports at all
- ``DCS-7508N`` — the 24-bay chassis they install into
"""

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# The generator ships inside a skill directory whose name is not a valid Python
# package name, so load it by file path — same approach as the converter tests.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = (
    _REPO_ROOT
    / "skills"
    / "infrahub-converting-netbox-device-types"
    / "scripts"
    / "materialize_module_ports.py"
)

_spec = importlib.util.spec_from_file_location("materialize_module_ports", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["materialize_module_ports"] = _mod
_spec.loader.exec_module(_mod)

ModulePortMaterializer = _mod.ModulePortMaterializer
PROVENANCE_PREFIX = _mod.PROVENANCE_PREFIX
REASON_DUPLICATE_IN_RUN = _mod.REASON_DUPLICATE_IN_RUN
REASON_KIND_NOT_IN_SCHEMA = _mod.REASON_KIND_NOT_IN_SCHEMA
REASON_NAME_TAKEN = _mod.REASON_NAME_TAKEN
REASON_NO_TARGET_KIND = _mod.REASON_NO_TARGET_KIND
REASON_POSITION_UNRESOLVED = _mod.REASON_POSITION_UNRESOLVED
REASON_UNKNOWN_CATEGORY = _mod.REASON_UNKNOWN_CATEGORY
REASON_UNNAMED = _mod.REASON_UNNAMED
POSITION_BAY_WITHOUT_POSITION = _mod.POSITION_BAY_WITHOUT_POSITION
POSITION_FROM_BAY = _mod.POSITION_FROM_BAY
POSITION_FROM_SLOT = _mod.POSITION_FROM_SLOT
POSITION_NO_BAY = _mod.POSITION_NO_BAY
is_ours = _mod.is_ours
peer = _mod.peer
peers = _mod.peers
plan_device = _mod.plan_device
provenance = _mod.provenance
resolve_name = _mod.resolve_name
resolve_position = _mod.resolve_position
scalar = _mod.scalar

STOCK_KINDS = {"InterfacePhysical"}
WITH_CONSOLE_KINDS = {"InterfacePhysical", "DcimConsoleInterface"}


# ---------------------------------------------------------------------------
# GraphQL response builders
# ---------------------------------------------------------------------------


def attr(value):
    """Wrap a value the way an Infrahub attribute arrives in GraphQL."""
    return {"value": value}


def one(node):
    """Wrap a cardinality-one relationship peer."""
    return {"node": node}


def many(nodes):
    """Wrap a cardinality-many relationship peer list."""
    return {"edges": [{"node": node} for node in nodes]}


def port(name, category="interface", port_type=None, mgmt_only=False, maximum_draw=None):
    """Build one DeviceModulePort node."""
    return {
        "name": attr(name),
        "category": attr(category),
        "port_type": attr(port_type),
        "mgmt_only": attr(mgmt_only),
        "maximum_draw": attr(maximum_draw),
    }


def module(
    serial,
    ports,
    position: str | None = "1",
    *,
    bay=True,
    slot=None,
    typename="DeviceLinecard",
):
    """Build one installed DeviceGenericModule node.

    Args:
        serial: The module's ``serial_number``.
        ports: Ports the module declares.
        position: Bay position, or ``None`` for a bay with a null position.
        bay: ``False`` to model a module with no ``module_bay`` at all.
        slot: Concrete-kind ``slot`` value, present only when the query's
            inline fragment is enabled.
        typename: GraphQL ``__typename`` of the concrete module kind.
    """
    node = {
        "id": f"mod-{serial}",
        "__typename": typename,
        "serial_number": attr(serial),
        "module_bay": one(
            {"id": f"bay-{position}", "name": attr(f"Slot {position}"), "position": attr(position)}
        )
        if bay
        else None,
        "ports": many(ports),
    }
    if slot is not None:
        node["slot"] = attr(slot)
    return node


def interface(name, description=""):
    """Build one existing DcimInterface node on the device."""
    return {
        "id": f"itf-{name}",
        "__typename": "InterfacePhysical",
        "name": attr(name),
        "description": attr(description),
    }


def device(name="dcs-7508n-01", modules=(), interfaces=(), device_id="device-uuid-1"):
    """Build one DcimDevice node."""
    return {
        "id": device_id,
        "name": attr(name),
        "interfaces": many(list(interfaces)),
        "modules": many(list(modules)),
    }


def response(*devices):
    """Wrap devices as the generator's query result."""
    return {"DcimDevice": many(list(devices))}


# ---------------------------------------------------------------------------
# Real NetBox module-type fixtures
# ---------------------------------------------------------------------------

#: module-types/Arista/DCS-7500-SUP2.yaml
SUP2_PORTS = [
    port("Console {module}", category="console", port_type="rj-45"),
    port("Management{module}/1", port_type="1000base-t", mgmt_only=True),
    port("Management{module}/2", port_type="1000base-t", mgmt_only=True),
]

#: module-types/Arista/DCS-7500R-36CQ.yaml
CQ36_PORTS = [
    port(f"Ethernet{{module}}/{index}/1", port_type="100gbase-x-qsfp28")
    for index in range(1, 37)
]

#: module-types/Juniper/EX-PWR-320-AC.yml
PWR_PORTS = [
    port("PSU {module}", category="power", port_type="iec-60320-c14", maximum_draw=320),
]

#: module-types/Arista/DCS-7508R-FM.yaml — declares no ports at all.
FM_PORTS: list[dict] = []

#: Not every published module type tokenises its port names. Synthetic, and
#: only the *shape* matters here: names with no ``{module}``.
UNTOKENISED_PORTS = [
    port("QSFP0", port_type="100gbase-x-qsfp28"),
    port("QSFP1", port_type="100gbase-x-qsfp28"),
]

#: device-types/Arista/DCS-7508N.yaml — 24 bays, three position styles.
DCS7508N_POSITIONS = (
    [str(index) for index in range(1, 11)]
    + [f"F{index}" for index in range(1, 7)]
    + [f"PSU-{index}" for index in range(1, 9)]
)


def names(plan):
    """Return the interface names a plan intends to create."""
    return [create.name for create in plan.creates]


def reasons(plan):
    """Return the skip reasons a plan recorded."""
    return [skip.reason for skip in plan.skips]


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def test_scalar_tolerates_missing_and_malformed_wrappers():
    assert scalar({"value": "Ethernet1"}) == "Ethernet1"
    assert scalar({"value": None}) is None
    assert scalar(None) is None
    assert scalar("not-a-wrapper") is None


def test_peer_returns_none_for_an_unset_single_relationship():
    assert peer({"node": {"id": "x"}}) == {"id": "x"}
    # Infrahub sends an unset cardinality-one relationship both of these ways.
    assert peer(None) is None
    assert peer({"node": None}) is None


def test_peers_returns_empty_for_unset_or_malformed_many_relationships():
    assert peers(many([{"id": "a"}, {"id": "b"}])) == [{"id": "a"}, {"id": "b"}]
    assert peers(None) == []
    assert peers({"edges": None}) == []
    assert peers({"edges": [{}, {"node": None}]}) == []


# ---------------------------------------------------------------------------
# Token substitution and position resolution
# ---------------------------------------------------------------------------


def test_token_is_substituted_with_the_bay_position():
    assert resolve_name("Ethernet{module}/1/1", "3") == "Ethernet3/1/1"
    # The SUP2's console port has a space before the token.
    assert resolve_name("Console {module}", "3") == "Console 3"
    # Free-form positions are substituted verbatim.
    assert resolve_name("Ethernet{module}/1/1", "F3") == "EthernetF3/1/1"


def test_untokenised_name_is_used_as_is_even_without_a_position():
    assert resolve_name("QSFP0", None) == "QSFP0"
    assert resolve_name("QSFP0", "3") == "QSFP0"


def test_tokenised_name_without_a_position_cannot_resolve():
    assert resolve_name("Ethernet{module}/1/1", None) is None


def test_position_comes_from_the_bay_when_set():
    assert resolve_position(module("S1", [], position="F3")) == ("F3", POSITION_FROM_BAY)


def test_bay_with_a_null_position_reports_that_specific_reason():
    assert resolve_position(module("S1", [], position=None)) == (
        None,
        POSITION_BAY_WITHOUT_POSITION,
    )


def test_module_with_no_bay_reports_that_specific_reason():
    assert resolve_position(module("S1", [], bay=False)) == (None, POSITION_NO_BAY)


def test_concrete_kind_slot_is_the_fallback_when_the_bay_gives_nothing():
    # Only reachable when the query's `... on DeviceLinecard` fragment is on.
    assert resolve_position(module("S1", [], bay=False, slot=7)) == ("7", POSITION_FROM_SLOT)
    assert resolve_position(module("S1", [], position=None, slot=7)) == ("7", POSITION_FROM_SLOT)


def test_bay_position_wins_over_the_concrete_slot():
    assert resolve_position(module("S1", [], position="F3", slot=7)) == ("F3", POSITION_FROM_BAY)


def test_blank_position_strings_are_not_treated_as_positions():
    assert resolve_position(module("S1", [], position="   ")) == (
        None,
        POSITION_BAY_WITHOUT_POSITION,
    )


# ---------------------------------------------------------------------------
# Category routing
# ---------------------------------------------------------------------------


def test_sup2_mixed_categories_on_the_stock_schema():
    """2 interfaces materialise; the console port has no kind to become."""
    plan = plan_device(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")]), STOCK_KINDS)

    assert names(plan) == ["Management3/1", "Management3/2"]
    assert reasons(plan) == [REASON_KIND_NOT_IN_SCHEMA]
    assert "DcimConsoleInterface" in plan.skips[0].detail
    assert all(create.kind == "InterfacePhysical" for create in plan.creates)


def test_mgmt_only_ports_get_the_management_role():
    plan = plan_device(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")]), STOCK_KINDS)
    assert {create.role for create in plan.creates} == {"management"}


def test_non_mgmt_ports_get_no_role():
    plan = plan_device(device(modules=[module("JPE-36CQ", CQ36_PORTS, "4")]), STOCK_KINDS)
    assert {create.role for create in plan.creates} == {None}


def test_console_port_materialises_when_the_schema_has_a_console_kind():
    plan = plan_device(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")]), WITH_CONSOLE_KINDS)

    assert plan.skips == []
    console = [create for create in plan.creates if create.kind == "DcimConsoleInterface"]
    assert [create.name for create in console] == ["Console 3"]
    # role stays unset: schema-library's role Dropdown has no `console` choice,
    # and an undeclared Dropdown value is rejected on write.
    assert console[0].role is None


def test_power_port_is_skipped_and_its_wattage_survives_into_the_reason():
    plan = plan_device(device(modules=[module("JN-PWR", PWR_PORTS, "PSU-2")]), WITH_CONSOLE_KINDS)

    assert plan.creates == []
    assert reasons(plan) == [REASON_NO_TARGET_KIND]
    assert "320 W" in plan.skips[0].detail
    assert "iec-60320-c14" in plan.skips[0].detail


@pytest.mark.parametrize("category", ["front", "rear"])
def test_pass_through_ports_are_skipped_without_inventing_a_mapping(category):
    plan = plan_device(
        device(modules=[module("S1", [port("Port {module}", category=category)], "1")]),
        WITH_CONSOLE_KINDS,
    )
    assert plan.creates == []
    assert reasons(plan) == [REASON_NO_TARGET_KIND]


def test_unrecognised_category_is_reported_rather_than_assumed_to_be_an_interface():
    plan = plan_device(
        device(modules=[module("S1", [port("X{module}", category="wireless")], "1")]),
        STOCK_KINDS,
    )
    assert plan.creates == []
    assert reasons(plan) == [REASON_UNKNOWN_CATEGORY]


def test_port_with_no_name_is_reported():
    plan = plan_device(device(modules=[module("S1", [port(None)], "1")]), STOCK_KINDS)
    assert reasons(plan) == [REASON_UNNAMED]


def test_no_kinds_available_skips_everything_rather_than_raising():
    plan = plan_device(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")]), set())
    assert plan.creates == []
    assert reasons(plan) == [REASON_KIND_NOT_IN_SCHEMA] * 3


# ---------------------------------------------------------------------------
# Whole-module cases
# ---------------------------------------------------------------------------


def test_36_port_linecard_resolves_every_port_to_its_own_name():
    plan = plan_device(device(modules=[module("JPE-36CQ", CQ36_PORTS, "4")]), STOCK_KINDS)

    assert len(plan.creates) == 36
    assert plan.skips == []
    assert names(plan)[0] == "Ethernet4/1/1"
    assert names(plan)[-1] == "Ethernet4/36/1"
    assert len(set(names(plan))) == 36


def test_module_declaring_no_ports_produces_nothing_and_reports_nothing():
    plan = plan_device(device(modules=[module("JPE-FM", FM_PORTS, "F1")]), STOCK_KINDS)
    assert plan.creates == []
    assert plan.skips == []


def test_untokenised_ports_materialise_even_with_no_bay_assigned():
    """A name that needs no position does not need a bay either."""
    plan = plan_device(device(modules=[module("S1", UNTOKENISED_PORTS, bay=False)]), STOCK_KINDS)

    assert names(plan) == ["QSFP0", "QSFP1"]
    assert plan.skips == []
    # No position was used, so provenance records the module only.
    assert plan.creates[0].description == f"{PROVENANCE_PREFIX} module S1"


def test_module_with_no_bay_skips_its_tokenised_ports_with_the_reason():
    plan = plan_device(
        device(modules=[module("JPE-SUP2", SUP2_PORTS, bay=False)]), WITH_CONSOLE_KINDS
    )

    assert plan.creates == []
    assert reasons(plan) == [REASON_POSITION_UNRESOLVED] * 3
    assert {skip.detail for skip in plan.skips} == {POSITION_NO_BAY}


def test_bay_with_null_position_skips_with_the_more_precise_reason():
    plan = plan_device(
        device(modules=[module("JPE-SUP2", SUP2_PORTS, position=None)]), WITH_CONSOLE_KINDS
    )

    assert reasons(plan) == [REASON_POSITION_UNRESOLVED] * 3
    assert {skip.detail for skip in plan.skips} == {POSITION_BAY_WITHOUT_POSITION}


def test_mixed_module_skips_only_the_ports_that_need_a_position():
    """A module with no bay still materialises its untokenised ports."""
    mixed = module("S1", UNTOKENISED_PORTS + [port("Ethernet{module}/1")], bay=False)
    plan = plan_device(device(modules=[mixed]), STOCK_KINDS)

    assert names(plan) == ["QSFP0", "QSFP1"]
    assert reasons(plan) == [REASON_POSITION_UNRESOLVED]


# ---------------------------------------------------------------------------
# Collisions and idempotency
# ---------------------------------------------------------------------------


def test_rerun_plans_the_same_upserts_and_adds_nothing():
    """Second run over its own output: same creates, no duplicates, no skips."""
    first = plan_device(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")]), STOCK_KINDS)

    already_there = [interface(create.name, create.description) for create in first.creates]
    second = plan_device(
        device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")], interfaces=already_there),
        STOCK_KINDS,
    )

    assert names(second) == names(first)
    assert reasons(second) == reasons(first)
    assert len(second.creates) == 2


def test_interface_created_by_someone_else_is_not_hijacked():
    """Upserting a foreign interface would take ownership, then delete it."""
    foreign = interface("Management3/1", "uplink to core, do not touch")
    plan = plan_device(
        device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")], interfaces=[foreign]),
        STOCK_KINDS,
    )

    assert names(plan) == ["Management3/2"]
    assert REASON_NAME_TAKEN in reasons(plan)
    taken = next(skip for skip in plan.skips if skip.reason == REASON_NAME_TAKEN)
    assert "Management3/1" in taken.detail


def test_a_foreign_interface_with_no_description_is_still_foreign():
    plan = plan_device(
        device(
            modules=[module("JPE-SUP2", SUP2_PORTS, "3")],
            interfaces=[interface("Management3/1", "")],
        ),
        STOCK_KINDS,
    )
    assert REASON_NAME_TAKEN in reasons(plan)


def test_provenance_marker_identifies_our_own_interfaces():
    assert is_ours(provenance("JPE-SUP2", "3"))
    assert is_ours(f"{PROVENANCE_PREFIX} module JPE-SUP2 bay 3")
    assert not is_ours("uplink to core")
    assert not is_ours("")
    assert not is_ours(None)


def test_two_modules_resolving_to_the_same_name_is_reported_not_silently_merged():
    """Two modules recorded in the same position is bad data, not a merge."""
    plan = plan_device(
        device(
            modules=[
                module("JPE-A", [port("Ethernet{module}/1")], "3"),
                module("JPE-B", [port("Ethernet{module}/1")], "3"),
            ]
        ),
        STOCK_KINDS,
    )

    assert names(plan) == ["Ethernet3/1"]
    assert reasons(plan) == [REASON_DUPLICATE_IN_RUN]
    assert "JPE-A" in plan.skips[0].detail


# ---------------------------------------------------------------------------
# Populated chassis
# ---------------------------------------------------------------------------


def test_populated_chassis_keeps_each_bay_position_to_its_own_module():
    """A DCS-7508N with five modules across three position styles."""
    chassis = device(
        modules=[
            module("SUP-A", SUP2_PORTS, "1"),
            module("SUP-B", SUP2_PORTS, "2"),
            module("LC-1", CQ36_PORTS, "3"),
            module("FM-1", FM_PORTS, "F1"),
            module("PWR-1", PWR_PORTS, "PSU-1"),
        ]
    )
    plan = plan_device(chassis, WITH_CONSOLE_KINDS)

    created = names(plan)
    # 2 supervisors x 3 ports + 36 linecard ports; the fabric module declares
    # none and the PSU's power port has no target kind.
    assert len(created) == 42
    assert len(set(created)) == 42, "positions must not collide across bays"

    assert {"Management1/1", "Management1/2", "Console 1"} <= set(created)
    assert {"Management2/1", "Management2/2", "Console 2"} <= set(created)
    assert "Ethernet3/1/1" in created and "Ethernet3/36/1" in created
    # No port ever borrows another bay's position.
    assert not [name for name in created if name.startswith("EthernetF1")]
    assert not [name for name in created if "PSU-1" in name]

    by_name = {create.name: create for create in plan.creates}
    assert by_name["Management1/1"].module_serial == "SUP-A"
    assert by_name["Management2/1"].module_serial == "SUP-B"
    assert by_name["Management2/1"].description == f"{PROVENANCE_PREFIX} module SUP-B bay 2"

    assert reasons(plan) == [REASON_NO_TARGET_KIND]


def test_every_chassis_bay_position_style_substitutes_cleanly():
    modules = [
        module(f"LC-{position}", [port("Ethernet{module}/1")], position)
        for position in DCS7508N_POSITIONS
    ]
    plan = plan_device(device(modules=modules), STOCK_KINDS)

    assert len(plan.creates) == 24
    assert plan.skips == []
    assert "Ethernet1/1" in names(plan)
    assert "EthernetF6/1" in names(plan)
    assert "EthernetPSU-8/1" in names(plan)


# ---------------------------------------------------------------------------
# port_type handling
# ---------------------------------------------------------------------------


def test_port_type_is_dropped_by_default_and_the_drop_is_counted():
    plan = plan_device(device(modules=[module("JPE-36CQ", CQ36_PORTS, "4")]), STOCK_KINDS)

    assert {create.port_type for create in plan.creates} == {None}
    assert plan.dropped_port_types == 36
    assert "36 port_type value(s) dropped" in plan.summary()


def test_port_type_is_carried_when_the_target_kind_has_an_attribute_for_it():
    plan = plan_device(
        device(modules=[module("JPE-36CQ", CQ36_PORTS, "4")]),
        STOCK_KINDS,
        port_type_attributes={"InterfacePhysical": "media_type"},
    )

    assert {create.port_type for create in plan.creates} == {"100gbase-x-qsfp28"}
    assert plan.dropped_port_types == 0


def test_skipped_ports_do_not_count_as_dropped_port_types():
    plan = plan_device(device(modules=[module("JN-PWR", PWR_PORTS, "PSU-2")]), STOCK_KINDS)
    assert plan.dropped_port_types == 0


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_summary_names_every_reason_with_its_count():
    plan = plan_device(
        device(
            modules=[
                module("JPE-SUP2", SUP2_PORTS, "3"),
                module("JN-PWR", PWR_PORTS, "PSU-1"),
                module("NO-BAY", [port("Ethernet{module}/1")], bay=False),
            ]
        ),
        STOCK_KINDS,
    )
    summary = plan.summary()

    assert "2 interface(s) planned" in summary
    assert "3 port(s) skipped" in summary
    assert REASON_KIND_NOT_IN_SCHEMA in summary
    assert REASON_NO_TARGET_KIND in summary
    assert REASON_POSITION_UNRESOLVED in summary


def test_skip_lines_name_the_module_the_port_and_the_reason():
    plan = plan_device(device(modules=[module("JN-PWR", PWR_PORTS, "PSU-2")]), STOCK_KINDS)
    line = plan.skips[0].render()

    assert "JN-PWR" in line
    assert "PSU {module}" in line
    assert "power" in line
    assert REASON_NO_TARGET_KIND in line
    assert "320 W" in line


def test_plan_records_the_device_it_belongs_to():
    plan = plan_device(device(name="dcs-7508n-02", modules=[]), STOCK_KINDS)
    assert plan.device_name == "dcs-7508n-02"
    assert plan.device_id == "device-uuid-1"
    assert plan.summary().startswith("dcs-7508n-02: ")


# ---------------------------------------------------------------------------
# SDK call shape
#
# Plan-level tests cannot catch a wrong relationship reference or a missing
# allow_upsert, which is where generators actually break. These drive
# generate() against a fake client to pin the payload shape. They do not
# replace an end-to-end run — see testing-integration.md.
# ---------------------------------------------------------------------------


class _FakeAttribute:
    def __init__(self, name):
        self.name = name


class _FakeNodeSchema:
    def __init__(self, attribute_names):
        self.attributes = [_FakeAttribute(name) for name in attribute_names]


class _FakeSchemaAPI:
    """Stands in for ``client.schema``, raising the SDK's own not-found error."""

    def __init__(self, kinds):
        self.kinds = kinds
        self.requested = []

    async def get(self, kind, branch=None):
        self.requested.append((kind, branch))
        if kind not in self.kinds:
            raise _mod.SchemaNotFoundError(identifier=kind)
        return _FakeNodeSchema(self.kinds[kind])


class _FakeNode:
    def __init__(self, kind, data):
        self.kind = kind
        self.data = data
        self.save_kwargs = None

    async def save(self, **kwargs):
        self.save_kwargs = kwargs


class _FakeClient:
    def __init__(self, kinds):
        self.schema = _FakeSchemaAPI(kinds)
        self.created = []

    async def create(self, kind, data):
        node = _FakeNode(kind, data)
        self.created.append(node)
        return node


def build_generator(kinds):
    """Build a generator bound to a fake client, bypassing the SDK constructor."""
    generator = ModulePortMaterializer.__new__(ModulePortMaterializer)
    generator.client = _FakeClient(kinds)
    generator.branch = "netbox-import"
    generator.logger = logging.getLogger("test.materialize_module_ports")
    return generator


def run_generate(generator, data):
    """Drive ``generate()`` to completion.

    ``asyncio.run`` rather than a pytest-asyncio marker: it keeps the suite
    runnable under a bare pytest with no plugin installed.
    """
    asyncio.run(generator.generate(data))


def test_generate_writes_the_expected_payload_shape():
    generator = build_generator(
        {"InterfacePhysical": ["name", "description", "mtu", "status", "role"]}
    )
    run_generate(generator, response(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")])))

    created = generator.client.created
    assert [node.kind for node in created] == ["InterfacePhysical"] * 2

    payload = created[0].data
    assert payload["name"] == "Management3/1"
    # A relationship must be a dict, never a bare string — a bare string is
    # read as an id and the server answers "Unable to find the node".
    assert payload["device"] == {"id": "device-uuid-1"}
    assert payload["description"].startswith(PROVENANCE_PREFIX)
    assert payload["role"] == "management"
    # port_type has nowhere to land on the stock kind, so it is absent.
    assert "port_type" not in payload


def test_generate_upserts_so_a_rerun_does_not_fail():
    generator = build_generator({"InterfacePhysical": ["name", "description"]})
    run_generate(generator, response(device(modules=[module("JPE-36CQ", CQ36_PORTS, "4")])))

    assert len(generator.client.created) == 36
    assert all(node.save_kwargs == {"allow_upsert": True} for node in generator.client.created)


def test_generate_writes_port_type_when_the_kind_has_the_configured_attribute(monkeypatch):
    monkeypatch.setattr(_mod, "PORT_TYPE_ATTRIBUTE", "media_type")
    generator = build_generator({"InterfacePhysical": ["name", "description", "media_type"]})
    run_generate(generator, response(device(modules=[module("JPE-36CQ", CQ36_PORTS[:1], "4")])))

    assert generator.client.created[0].data["media_type"] == "100gbase-x-qsfp28"


def test_generate_drops_port_type_when_the_configured_attribute_is_absent(monkeypatch):
    """A wrong PORT_TYPE_ATTRIBUTE must degrade, not fail every create."""
    monkeypatch.setattr(_mod, "PORT_TYPE_ATTRIBUTE", "not_a_real_attribute")
    generator = build_generator({"InterfacePhysical": ["name", "description"]})
    run_generate(generator, response(device(modules=[module("JPE-36CQ", CQ36_PORTS[:1], "4")])))

    payload = generator.client.created[0].data
    assert "not_a_real_attribute" not in payload
    assert payload["name"] == "Ethernet4/1/1"


def test_generate_probes_each_candidate_kind_on_the_run_branch():
    generator = build_generator({"InterfacePhysical": ["name"]})
    run_generate(generator, response(device(modules=[module("JPE-SUP2", SUP2_PORTS, "3")])))

    requested = {kind for kind, _ in generator.client.schema.requested}
    assert requested == {"DcimConsoleInterface", "InterfacePhysical"}
    assert {branch for _, branch in generator.client.schema.requested} == {"netbox-import"}


def test_generate_creates_nothing_when_no_device_matched():
    generator = build_generator({"InterfacePhysical": ["name"]})
    run_generate(generator, {"DcimDevice": many([])})
    assert generator.client.created == []


def test_generate_creates_nothing_when_the_response_is_empty():
    generator = build_generator({"InterfacePhysical": ["name"]})
    run_generate(generator, {})
    assert generator.client.created == []


def test_generate_handles_every_device_in_the_response():
    generator = build_generator({"InterfacePhysical": ["name"]})
    run_generate(generator, 
        response(
            device(name="chassis-a", modules=[module("A", [port("Ethernet{module}/1")], "1")]),
            device(
                name="chassis-b",
                modules=[module("B", [port("Ethernet{module}/1")], "2")],
                device_id="device-uuid-2",
            ),
        )
    )

    created = {node.data["name"]: node.data["device"] for node in generator.client.created}
    assert created == {
        "Ethernet1/1": {"id": "device-uuid-1"},
        "Ethernet2/1": {"id": "device-uuid-2"},
    }
