# Materialising Module Ports as Device Interfaces

The converter turns NetBox `module-types/` into module
type objects and, where the profile configures it,
module templates. What it cannot do is resolve
`{module}`.

93.9% of published module-type component names carry
that token, which NetBox substitutes with the bay
position when the module is installed. A template is
not bound to a bay, so at conversion time the position
is genuinely unknown — see
[extending-your-schema.md](./extending-your-schema.md#the-module-position-token).

This is the piece that closes the gap: a generator that
runs *after* install, reads the bay position off the
installed module, and creates the real device
interfaces.

| File | What it is |
| ---- | ---------- |
| [`scripts/materialize_module_ports.py`](./scripts/materialize_module_ports.py) | The generator |
| [`scripts/materialize_module_ports.gql`](./scripts/materialize_module_ports.gql) | Its query |
| `tests/scripts/test_materialize_module_ports.py` | Its tests |

## Why a generator and not a template

A `DcimModulePort` is a **declaration**: it records
the port a module type provides, parented by the
module, with `{module}` still literal. It is
deliberately not a `DcimInterface`.

`DcimInterface.device` is a mandatory `Parent`, and
Infrahub requires a relationship used in a uniqueness
constraint to be mandatory — every interface kind is
keyed `[device, name__value]` with a
`device__name__value` human_friendly_id. Relaxing
`device` so an interface could hang off a module
instead fails schema validation outright:

```text
DcimConsoleInterface.uniqueness_constraints: cannot use device
relationship, relationship must be mandatory. (`device`)
```

So the declaration stays on the module and something
has to create the device-side interface. That
something has to be a generator rather than a template
for one reason: the bay position is only known once the
module is installed.

Schema prerequisites, in load order: `base/dcim.yml` →
`extensions/device_module/device_module.yml` →
`extensions/device_module/device_module.yml` →
`extensions/module_port/module_port.yml`.

## What it creates, and what it refuses to

Per device, for each installed module: resolve the bay
position, substitute the token, and route by
`port.category`.

| `category` | Outcome |
| ---------- | ------- |
| `interface` | `InterfacePhysical` on `device.interfaces`; `role: management` when `mgmt_only` |
| `console` | A console interface kind — **only if the loaded schema has one** |
| `power` | Skipped and reported. A power inlet is not an interface |
| `front` / `rear` | Skipped and reported. Pass-through patch positions need their own node |

Routing is by category **and** schema availability.
Every candidate kind is probed with
`client.schema.get` before use, so the generator never
assumes a console kind exists — stock schema-library
has none, and that is a logged skip rather than a
failed run. Add one (a node inheriting `DcimInterface`,
per
[Gap 1](./extending-your-schema.md#gap-1-a-whole-component-list-is-skipped))
and the same run starts materialising console ports
with no code change.

### Where `port_type` goes: nowhere, by default

`DcimModulePort.port_type` holds a NetBox slug
(`1000base-t`, `rj-45`, `iec-60320-c14`). Stock
`InterfacePhysical` has **no media-type attribute** —
its own attribute list is empty and the `DcimInterface`
generic it inherits declares only `name`,
`description`, `mtu`, `status`, `role`.

So `port_type` is **dropped**, and the count of dropped
values is reported per device rather than hidden. If
your schema has somewhere for it, set
`PORT_TYPE_ATTRIBUTE` to that attribute's name; it is
validated against the target kind's real attribute list
at run time and disabled with a warning if absent, so a
wrong name degrades to the default instead of failing
every create. No attribute name is guessed.

### `role` on console ports is deliberately unset

`role` is a `Dropdown` and Infrahub rejects an
undeclared value. Schema-library's choices are `lag`,
`core`, `cust`, `access`, `management`, `peering`,
`upstream` — there is **no `console`**. So
`CONSOLE_ROLE` defaults to `None`; a schema that adds a
console interface kind may or may not also add the
choice. Check yours before setting it.

## The unresolvable cases

None of these crash, and none pass silently.

| Case | What happens |
| ---- | ------------ |
| Port name has no `{module}` token | Valid — the name is used as-is. No position needed, so a module with no bay still materialises these |
| Module has no `module_bay` | Tokenised ports skipped, reason `module has no module_bay` |
| `module_bay.position` is null | Tokenised ports skipped, reason `module_bay set but position is null` |
| Resolved name collides with a foreign interface | Skipped, and the foreign interface is left untouched |
| Two modules resolve to the same name | First wins, second skipped naming the module that claimed it |
| Unrecognised `category` | Skipped rather than assumed to be an interface |

Each skip is logged individually with the module
serial, the port name, the category, and the reason,
plus a per-device summary counting reasons. A silent
skip reads as "nothing to do", which is the failure
this generator would otherwise get blamed for.

Bay position resolution prefers
`module_bay.position`. It falls back to a concrete-kind
`slot` value when the query's inline fragment is
enabled — see [Query](#query) below.

## Idempotency and provenance

`run()` wraps `generate()` in a tracking context with
`delete_unused_nodes=True`, and every `save()` uses
`allow_upsert=True` — the mechanism
[tracking-idempotent.md](../infrahub-managing-generators/rules/tracking-idempotent.md)
prescribes. Re-running resolves the same names and
updates in place.

Tracking alone cannot distinguish "an interface this
generator owns" from "an interface someone else created
at the same name", and the two need opposite handling.
So every interface the generator writes carries a
marker in `description`:

```text
[module-port] module JPE12345678 bay 3
```

A resolved name colliding with an interface **without**
that marker is skipped and reported. Upserting it would
silently take ownership of somebody else's interface —
and the next run's cleanup would then delete it.

> **The flip side of `delete_unused_nodes=True`:** an
> interface this generator created on a previous run
> and does not recreate on this one gets **deleted**.
> That is correct desired-state behaviour when a module
> is pulled, and it is also what happens when a bay
> position becomes null. The skip log is where that
> shows up — read it before assuming a quiet run was a
> no-op.

## Query

`scripts/materialize_module_ports.gql`, rooted at
`DcimDevice` — `modules` and `module_bays` are extended
onto the `DcimPhysicalDevice` generic while `name` and
`interfaces` live on `DcimGenericDevice`, and
`DcimDevice` inherits both.

It fetches, per device: the device name and id, its
existing interface names and descriptions (for the
collision check), its installed modules, each module's
`module_bay.position`, and each module's ports with
`name`, `category`, `mgmt_only`, `port_type`, and
`maximum_draw`.

### Unions and inline fragments

`device.modules` peers the **generic**
`DcimGenericModule`, so the node type is a GraphQL
interface. Everything the generator needs is declared
on that generic — `serial_number` and `description` on
the generic itself, `ports` and `module_bay` extended
onto it by `module_port.yml` and `module_bay.yml` —
which is why they select directly.

Fields living only on a **concrete** module kind need
an inline fragment. Selecting one on the interface
fails the whole query:

```text
Cannot query field 'slot' on type 'DcimGenericModule'.
```

The rule is
[queries-union-fragments.md](../infrahub-managing-transforms/rules/queries-union-fragments.md).
The one such field this generator can use is
`DeviceLinecard.slot` — a fallback bay position for a
linecard installed with no `module_bay` set:

```graphql
... on DeviceLinecard {
  slot {
    value
  }
}
```

It ships **commented out**, because the inverse failure
is just as absolute: a fragment on a type absent from
the loaded schema fails the query with
`Unknown type 'DeviceLinecard'`, and that kind lives in
schema-library's *experimental* tree. Uncomment it once
`DeviceLinecard` is loaded — the generator already
reads `slot` defensively, so nothing else changes.

Note the fallback only helps numeric bays: `slot` is a
`Number`, so it can never produce `F3` or `PSU-2`.

`interfaces` peers the generic `DcimInterface`, but
`name` and `description` are declared on that generic
(`InterfacePhysical` adds no attributes of its own), so
they select directly too.

## Registration

Copy the two files into the repo Infrahub syncs, then:

```yaml
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
      name: name__value
```

`generator_definitions` carries a top-level `query:` —
the opposite of `check_definitions`. `targets` must be
a **`CoreGeneratorGroup`**; a `CoreStandardGroup` of
the same name parses fine and then never triggers. See
[registration-config.md](../infrahub-managing-generators/rules/registration-config.md).

### The `parameters` key is doing two jobs

`name: name__value` does **not** read as "bind the
`$name` variable to the `name__value` attribute", even
though it looks like it. Under `infrahubctl generator`
(SDK 1.19.0, `infrahub_sdk/ctl/generator.py`) only the
**first key** is read, and it is used twice:

```python
identifier = list(generator_config.parameters.keys())[0]
...
attribute = getattr(member.peer, identifier)      # 1. a node attribute name
check_parameter = {identifier: attribute.value}   # 2. the GraphQL variable name
```

So the key must simultaneously be an attribute on every
member of the target group **and** the variable the query
declares. `name` is both. The value (`name__value`) is
never read on this path.

Getting it wrong is not a quiet failure, at least:

```text
$ infrahubctl generator materialize_module_ports --branch test
Error: 'InfrahubNode' object has no attribute 'device_name'
```

> **The server does not resolve `parameters` the same
> way.** In a proposed change the backend calls
> `member.extract(params=generator_definition.parameters)`
> (`backend/infrahub/proposed_change/tasks.py`), passing
> the whole mapping rather than just its keys — so there
> the value *is* meaningful and the key is a plain
> variable name. `name: name__value` is chosen because it
> satisfies both readings; a key that is not also a node
> attribute works in-server and breaks in the CLI. Only
> the CLI half of this is verified against source here.

Passing the variable positionally skips the group and
identifier logic altogether — useful for a one-device
smoke test, and it ignores `targets` entirely:

```bash
infrahubctl generator materialize_module_ports name=lon-dc1-chassis-01 --branch test
```

### Populating the target group

`CoreGeneratorGroup.members` peers `CoreNode`, which has
no `human_friendly_id`, so members cannot be named in an
object file. This looks reasonable and does not work:

```yaml
spec:
  kind: CoreGeneratorGroup
  data:
    - name: devices_with_modules
      members:
        - lon-dc1-chassis-01      # no HFID on CoreNode to resolve against
```

```text
['CoreGeneratorGroupUpsert'] Unable to find the node
lon-dc1-chassis-01 / CoreNode in the database.
```

Create the group in the object file with no members, then
add them through the SDK. `fetch()` is mandatory before
touching the relationship, and `add()` takes **one peer
per call** — see
[python-multi-peer-add.md](../infrahub-managing-generators/rules/python-multi-peer-add.md):

```python
group = await client.get(
    kind="CoreGeneratorGroup", name__value="devices_with_modules", branch=branch
)
await group.members.fetch()   # without this: UninitializedError — "Must call
                              # fetch() on RelationshipManager before editing members"

for device_name in ("lon-dc1-chassis-01", "lon-dc1-access-01"):
    device = await client.get(kind="DcimDevice", name__value=device_name, branch=branch)
    group.members.add(device)

await group.save(allow_upsert=True)
```

## Installing a module

The generator can only resolve ports that exist, and a
module created the obvious way has none. Worth reading
before concluding the generator is broken.

**Ports come from the module template, and
`object_template` applies only at creation.** Port
declarations hang off `TemplateDeviceLinecard`, not off
the module *type*. A `DeviceLinecard` created without
`object_template` comes up with `ports=0`, so the
generator finds nothing, resolves nothing, and reports a
clean no-op — which reads as "it does not work" rather
than "this module has no ports".

```yaml
spec:
  kind: DeviceLinecard
  data:
    - serial_number: JPE-SUP2-0001
      object_template: mod-DCS-7500-SUP2   # REQUIRED, or ports=0
      linecard_type: DCS-7500-SUP2
      module_type: DCS-7500-SUP2
      module_bay: ["lon-dc1-chassis-01", "Slot 1"]
```

Adding `object_template` to a module that already exists
and re-loading does **not** backfill the ports. The
modules have to be deleted and recreated.

**The module→device link has to be set from the device
side.** `DcimGenericModule.device` peers
`DcimPhysicalDevice`, a generic with no `name` and so no
`human_friendly_id` — there is nothing for a name in an
object file to resolve against. Set it from
`DcimDevice.modules` instead, whose peer
`DcimGenericModule` *is* keyed on `serial_number__value`.
That document has to restate the device's mandatory
`status` and `location`:

```yaml
spec:
  kind: DcimDevice
  data:
    - name: lon-dc1-chassis-01
      status: active
      location: lon-dc1
      modules:
        - JPE-SUP2-0001
        - JPE-SUP2-0002
```

Load order: device types and module types → templates →
devices → module bays → modules → the group. Then run the
generator.

## Testing

`tests/scripts/test_materialize_module_ports.py` — 49
tests over real published fixtures:

| Fixture | Covers |
| ------- | ------ |
| `DCS-7500-SUP2` | Mixed categories: 2 mgmt interfaces + 1 console port |
| `DCS-7500R-36CQ` | 36 tokenised interfaces, all resolving to their own name |
| `EX-PWR-320-AC` | A power port skipped with its 320 W in the reason |
| `DCS-7508R-FM` | A module declaring no ports at all |
| `DCS-7508N` | A 24-bay chassis: `1`–`10`, `F1`–`F6`, `PSU-1`–`PSU-8` |

Plus re-run idempotency, foreign-name collisions, the
missing-bay and null-position cases, untokenised names,
and the SDK payload shape.

```bash
uv run invoke test          # the whole suite
uv run --group test pytest tests/scripts/test_materialize_module_ports.py
```

The SDK lives in an opt-in `test` dependency group, which
is why the `--group test` is needed when invoking pytest
directly.

Those tests pin the planning logic and the payload
shape, and they do not cover the wire protocol. Per
[testing-integration.md](../infrahub-managing-generators/rules/testing-integration.md),
run it end to end before declaring it done:

```bash
infrahubctl branch create module-ports
infrahubctl generator list
infrahubctl generator run materialize_module_ports --branch module-ports
```

Then check the created interfaces exist on the device
and that `description` carries the provenance marker.
Run it a second time and confirm the count does not
change — that is the idempotency claim, and it is the
one unit tests cannot make for you.

## Out of scope

- **Which module type belongs in which bay.** NetBox
  device-type definitions do not record it; that is
  human or design input.
- **Modules that themselves contain bays**
  (`A9K-AC-PEM-V3` has 4). Nested bays are not
  modelled.
- **Changing `DcimInterface` to allow a non-device
  parent.** Ruled out above — it fails schema
  validation.
