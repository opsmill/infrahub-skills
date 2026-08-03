# Extending your schema to close coverage gaps

The coverage report names what did not convert. This
page turns each of those lines into a schema change.

Work through it only for the gaps you actually care
about. Modelling console ports you will never query is
cost, not completeness — see
[the YAGNI rules](../infrahub-auditing-repo/rules/)
if you are unsure whether a gap is worth closing.

> Docs:
> [Schema extensions](https://docs.infrahub.app/schema/extensions)
> · [Node reference](https://docs.infrahub.app/reference/schema/node)
> · [Attribute reference](https://docs.infrahub.app/reference/schema/attribute)
> · [Relationship reference](https://docs.infrahub.app/reference/schema/relationship)

## Check for an existing node first

Before writing any schema, look for a node that already
covers the gap. Two places to check, in this order:

**1. The schema you already load.** Grep for the
concept rather than the exact name — a console port may
be modelled as a kind of interface:

```bash
grep -rn "ConsoleInterface\|ConsolePort\|ModuleBay" schemas/
ls schemas/extensions/ 2>/dev/null
```

**2. The OpsMill schema-library extensions**, if the
project builds on it:

```bash
ls schema-library/extensions/
```

| NetBox list | Existing coverage | Notes |
| ----------- | ----------------- | ----- |
| `console-ports` | `DcimConsoleInterface` in infrahub-demo-dc's `extensions/console/` | Inherits `DcimInterface`, so no new relationship — see [below](#console-ports-usually-need-no-schema-change) |
| `module-bays` | Partial — `extensions/modules/` in schema-library | Models modules and module *types*, not bays — see [below](#module-bays-what-the-modules-extension-does-and-does-not-give-you) |
| `inventory-items` | Partial — `extensions/modules/` | `DeviceGenericModuleType` covers part numbers |
| `front-ports` / `rear-ports` | `extensions/patch_panel/` | Patch-panel oriented |
| `interfaces` (optics) | `extensions/sfp/` | Transceivers, not interface media type |

Finding one turns a schema change into a profile
change, which is far cheaper and does not touch the
user's source of truth.

## Console ports usually need no schema change

The commonest gap has the cheapest fix, because a
console port is *a kind of interface*. Where the schema
models it as a node inheriting the interface generic —
as infrahub-demo-dc's `DcimConsoleInterface` does —
the device's existing `interfaces` Component
relationship already carries it. Infrahub therefore
already generates `TemplateDcimConsoleInterface`, and
only the mapping profile is missing:

```yaml
components:
  interfaces:
    kind: TemplateInterfacePhysical
    relationship: interfaces
    template_name: "{template_name}__{name}"
    fields:
      name: name
  console-ports:
    kind: TemplateDcimConsoleInterface
    relationship: interfaces          # same relationship, by inheritance
    template_name: "{template_name}__console__{name}"
    fields:
      name: name
```

Two things this depends on, both covered by
[mapping-shared-relationships.md](./rules/mapping-shared-relationships.md):
the two lists share one relationship, so the output has
to accumulate blocks rather than overwrite; and their
template names must not collide, hence the `__console__`
infix.

Residual loss: NetBox console `type` (`rj-45`,
`usb-mini-b`) has nowhere to go —
`DcimConsoleInterface` has `speed` and `port`, not a
port type. One Dropdown attribute closes it if you care;
see [Gap 2](#gap-2-a-field-is-dropped).

If your schema has no console node at all, that is
[Gap 1](#gap-1-a-whole-component-list-is-skipped).

## Module bays: what the modules extension does and does not give you

Modular chassis convert to an empty template — a
DCS-7508N has 24 module bays and zero interfaces,
because every port lives on a line card. This is the
largest single gap in the library and the honest answer
has three parts.

**What schema-library's `extensions/modules/` provides:**

| Kind | Represents | Templatable? |
| ---- | ---------- | ------------ |
| `DeviceGenericModule` | An *installed* module, keyed by a unique `serial_number` | **Yes** — see below |
| `DeviceGenericModuleType` | The module model (name, part number, manufacturer) | Not a device component |
| `DcimPhysicalDevice.modules` | `Component` relationship to installed modules | Yes, generates `TemplateDeviceGenericModule` |

Both are **generics**, so you also need a concrete node
inheriting them — and that node needs
`generate_template: true` — before anything can be
instantiated or templated.

> **The unique serial number is not a blocker.** It is
> tempting to conclude that a module cannot be templated
> because `serial_number` is `unique: true` and is the
> generic's `human_friendly_id`. It can. Infrahub omits
> unique attributes from a generated template entirely
> and re-keys it on `template_name`, so
> `TemplateDeviceLinecard` has no `serial_number` and is
> created without one — the serial is supplied per
> installed module. See
> [concepts.md](./concepts.md#unique-attributes-do-not-exist-on-a-template).

**What genuinely is missing** is a component
relationship: `DeviceGenericModule` has none, so a
module template has nowhere to put the module's ports
until you add one ([Gap 1](#gap-1-a-whole-component-list-is-skipped)).

**Why none of this maps to NetBox module bays.** A
NetBox module bay is a *slot* — `name`, `label`,
`position`:

```yaml
module-bays:
  - name: Slot 1
    label: Supervisor
    position: '1'
```

The extension models what is *installed*, not the slot
that holds it. A device type declares that a chassis
*has* eight line-card slots; it says nothing about which
line cards are in them, which is what
`DeviceGenericModule` records. Mapping bays onto modules
would assert an inventory the input does not contain.

**What does map.** NetBox publishes module types as a
**separate input directory**, `module-types/`, and those
line up with `DeviceGenericModuleType` cleanly. The
converter reads them — see
[Converting module types](#converting-module-types).

**Recommendation.** If chassis matter to you:

1. Load `extensions/modules/modules.yml` and define a
   concrete node inheriting `DeviceGenericModuleType`
   (`experimental/modules_linecards/linecard.yml` has a
   worked `DeviceLinecardType` / `DeviceLinecard` pair).
2. Convert `module-types/` with the
   `schema-library-modules.yml` profile.
3. Model bays only if you need slot-level accounting —
   that is a new node (`name`, `position`, plus a
   Component relationship), following
   [Gap 1](#gap-1-a-whole-component-list-is-skipped).

If chassis are not in scope, leaving them reported as
skipped is the right answer. Say so rather than
producing an empty template that looks like a working
one.

## Converting module types

Module types are a second NetBox input family. The
converter tells them apart by the absence of `slug` —
no published module type carries one — so a mixed tree
converts in a single pass:

```bash
python scripts/netbox_to_infrahub_templates.py \
  devicetype-library/device-types/Arista/ \
  devicetype-library/module-types/Arista/ \
  --mapping scripts/mappings/schema-library-modules.yml \
  --output-dir ./generated
```

Output gains two slots; files with nothing in them are
not written:

| File | Kind |
| ---- | ---- |
| `04_module_types.yml` | `module_type.kind` |
| `05_module_templates.yml` | `module_type.template.kind`, when configured |

### The minimum profile

```yaml
module_type:
  kind: DeviceLinecardType        # YOUR concrete node, not the generic
  manufacturer_relationship: manufacturer
  key: "{model}"                  # module types have no slug
  fields:
    model: name
    part_number: part_number
    description:
      target: description
      fallback: comments
```

That is all the stock schema supports, and it is worth
being blunt about why: a NetBox module type is mostly
its component list — the ports the module provides —
and neither `DeviceGenericModuleType` nor
`DeviceGenericModule` has **any component
relationship**. Every `interfaces`, `power-ports`, and
`front-ports` entry is reported as skipped. You get a
catalogue of module models, not their ports.

Note what is *not* the obstacle: the unique
`serial_number`. Module templates work fine — Infrahub
omits unique attributes from templates and keys them on
`template_name`. The missing piece is somewhere to put
the ports.

### Carrying the components too

Two changes to your concrete module node:

1. `generate_template: true`, so `Template<YourModule>`
   is generated at all.
2. A `Component` relationship that can hold ports
   ([Gap 1](#gap-1-a-whole-component-list-is-skipped)).

```yaml
nodes:
  - name: Linecard
    namespace: Device
    generate_template: true          # generates TemplateDeviceLinecard
    inherit_from:
      - DeviceGenericModule
    relationships:
      - name: interfaces
        peer: DcimInterface
        identifier: linecard__interface
        cardinality: many
        kind: Component              # generates the port sub-templates
```

Then add the template half of the profile:

```yaml
module_type:
  kind: DeviceLinecardType
  manufacturer_relationship: manufacturer
  key: "{model}"
  position_placeholder: "1"
  fields:
    model: name
  template:
    kind: TemplateDeviceLinecard
    template_name: "module__{model}"
    module_type_relationship: linecard_type
  components:
    interfaces:
      kind: TemplateInterfacePhysical
      relationship: interfaces
      template_name: "{template_name}__{name}"
      fields:
        name: name
```

Declaring `components` without `template` is rejected —
components hang off a template, and without one they
would silently go nowhere.

### The `{module}` position token

93.9% of published module-type component names contain
`{module}`, which NetBox substitutes with the bay
position when the module is installed:

```yaml
interfaces:
  - name: Ethernet{module}/1
power-ports:
  - name: '{module}'
```

A template is not bound to a bay, so the token cannot
be resolved at conversion time. Two options:

- **Leave it** (default). Names keep the literal
  `{module}`, the information survives, and the report
  says how many names carry it. Right when something
  downstream will substitute it.
- **Set `position_placeholder`** to a bay position.
  `Ethernet{module}/1` with `position_placeholder: "1"`
  becomes `Ethernet1/1`. Right when you are modelling a
  specific populated slot, and wrong as a blanket
  default — it silently asserts every module sits in
  the same bay.

Neither is a substitute for modelling bays. If you need
per-slot accuracy, the template has to be per-slot.

## Two shapes of gap

The report distinguishes them, and they need different
fixes:

| Report line | Meaning | Fix |
| ----------- | ------- | --- |
| `Skipped \`console-ports\` (2 entries)` | No node exists for this component at all | [Add a component node](#gap-1-a-whole-component-list-is-skipped) |
| `Dropped from \`interfaces\`: \`type\`` | The node exists but has no such attribute | [Add an attribute](#gap-2-a-field-is-dropped) |
| `Shadowed: … lost to …` | Two NetBox fields competed for one attribute | [Add a second attribute](#gap-3-a-value-is-shadowed) |

## Gap 1: a whole component list is skipped

Skipped lists mean the schema has no node for that
component, so there is nothing for a component
template to be generated from.

Closing it takes three pieces:

1. A **node** for the component.
2. A **`Parent`** relationship from it to the device.
3. A **`Component`** relationship back from the device,
   sharing the same `identifier`.

The Component/Parent pair is what makes Infrahub
generate `TemplateDcimConsolePort`. Miss it and you
get a node with no template.

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

nodes:
  - name: ConsolePort
    namespace: Dcim
    label: Console Port
    icon: mdi:serial-port
    display_label: name__value
    human_friendly_id:
      - device__name__value
      - name__value
    uniqueness_constraints:
      - [device, name__value]
    attributes:
      - name: name
        kind: Text
        order_weight: 1000
      - name: port_type
        kind: Dropdown
        optional: true
        order_weight: 1100
        choices:
          - name: rj-45
            label: RJ-45
          - name: usb-mini-b
            label: USB Mini-B
          - name: usb-c
            label: USB Type C
    relationships:
      - name: device
        peer: DcimGenericDevice
        identifier: device__consoleport   # must match the other side
        optional: false                   # a port with no device is meaningless
        cardinality: one
        kind: Parent
        order_weight: 1050

extensions:
  nodes:
    - kind: DcimGenericDevice
      relationships:
        - name: console_ports
          peer: DcimConsolePort
          identifier: device__consoleport # same identifier, both sides
          optional: true
          cardinality: many
          kind: Component
          order_weight: 1800
```

Using `extensions:` rather than editing the upstream
node keeps your changes separable from the
schema-library you pulled in — the library can be
updated without stomping your additions.

> Docs: [Schema extensions](https://docs.infrahub.app/schema/extensions)
> · [Node extension reference](https://docs.infrahub.app/reference/schema/node-extension)

Then add the list to the mapping profile:

```yaml
components:
  console-ports:
    kind: TemplateDcimConsolePort
    relationship: console_ports          # the Component relationship name
    template_name: "{template_name}__console__{name}"
    fields:
      name: name
      type: port_type
```

### What each NetBox list needs

Same recipe, different fields. `relationship` is the
name you give the Component relationship on the device.

| NetBox list | Suggested node | NetBox fields worth modelling |
| ----------- | -------------- | ----------------------------- |
| `console-ports` | `DcimConsolePort` | `name`, `type` |
| `console-server-ports` | `DcimConsoleServerPort` | `name`, `type` |
| `power-ports` | `DcimPowerPort` | `name`, `type`, `maximum_draw`, `allocated_draw` |
| `power-outlets` | `DcimPowerOutlet` | `name`, `type`, `power_port`, `feed_leg` |
| `front-ports` | `DcimFrontPort` | `name`, `type`, `rear_port`, `rear_port_position` |
| `rear-ports` | `DcimRearPort` | `name`, `type`, `positions` |
| `module-bays` | `DcimModuleBay` | `name`, `position` |
| `device-bays` | `DcimDeviceBay` | `name` |
| `inventory-items` | `DcimInventoryItem` | `name`, `manufacturer`, `part_id` |

Three of these carry a wrinkle:

- **`power-outlets`** reference a `power_port` by name
  on the same device. Modelling that faithfully means a
  relationship between two component nodes; the
  converter maps it as text unless you add one.
- **`front-ports`** reference a `rear_port` the same
  way, plus a position index.
- **`module-bays`** are how modular chassis carry their
  ports, and the schema-library modules extension does
  not cover them the way you would expect — see
  [the module-bay section](#module-bays-what-the-modules-extension-does-and-does-not-give-you)
  before modelling anything.

Before adding any of them, re-read
[Check for an existing node first](#check-for-an-existing-node-first) —
console ports and module bays in particular are usually
better served by something that already exists.

## Gap 2: a field is dropped

A dropped field means the node exists but has no
attribute to hold that value. The commonest by far is
`interfaces.type` — NetBox records the media type of
every port and stock `InterfacePhysical` has nowhere
to put it (86.5% of the library hits this).

Add the attribute with `extensions:`:

```yaml
extensions:
  nodes:
    - kind: InterfacePhysical
      attributes:
        - name: interface_type
          label: Interface Type
          kind: Dropdown
          optional: true
          order_weight: 1150
          choices:
            - name: 1000base-t
              label: 1GE (RJ-45)
            - name: 10gbase-t
              label: 10GE (RJ-45)
            - name: 10gbase-x-sfpp
              label: 10GE (SFP+)
            - name: 25gbase-x-sfp28
              label: 25GE (SFP28)
            - name: 40gbase-x-qsfpp
              label: 40GE (QSFP+)
            - name: 100gbase-x-qsfp28
              label: 100GE (QSFP28)
```

```yaml
components:
  interfaces:
    fields:
      name: name
      type: interface_type
```

**A `Dropdown` only accepts values it declares as
choices.** NetBox uses well over a hundred interface
type slugs; mapping `type` onto a Dropdown missing one
fails the load for every device type using it. Two safe
routes:

- Enumerate only the types you use, and keep the
  mapping until the report shows a value you have not
  declared.
- Use `kind: Text` instead, accepting any value, and
  trade UI validation for coverage.

Run the converter across your real input first and read
the report — it tells you which values actually appear
before you commit to a list.

Other frequently dropped top-level fields:

| NetBox field | Suggested attribute | Kind |
| ------------ | ------------------- | ---- |
| `airflow` | `airflow` on the device type | `Dropdown` (10 values) |
| `subdevice_role` | `subdevice_role` | `Dropdown` (`parent`, `child`) |
| `is_powered` | `is_powered` | `Boolean` |
| `poe_mode` / `poe_type` | `poe_mode` / `poe_type` on the interface | `Dropdown` |

> Docs:
> [Nodes and attributes](https://docs.infrahub.app/schema/nodes-and-attributes)
> · [Attribute reference](https://docs.infrahub.app/reference/schema/attribute)

## Gap 3: a value is shadowed

Shadowing means two NetBox fields competed for one
Infrahub attribute and the loser was discarded. Either
accept it, or give the loser its own home:

```yaml
extensions:
  nodes:
    - kind: DcimDeviceType
      attributes:
        - name: datasheet
          kind: URL
          optional: true
          order_weight: 1900
```

```yaml
device_type:
  fields:
    description: description     # no longer competing
    comments: datasheet
```

Note `kind: URL` — Infrahub has typed attribute kinds
beyond `Text`, and using the specific one buys
validation and better UI rendering.

## After changing the schema

Schema changes are migrations. Load onto a branch and
review before merging:

```bash
infrahubctl branch create schema-netbox-import
infrahubctl schema load schemas/dcim.yml --branch schema-netbox-import
infrahubctl schema load schemas/dcim-netbox-extensions.yml --branch schema-netbox-import
```

Then re-run the converter with the updated profile and
confirm the report shows the list under *converted*
rather than *skipped*.

Some changes are not safely reversible once data
exists — narrowing an attribute, removing a
relationship, or changing a kind can drop values. Read
[Schema migrations](https://docs.infrahub.app/schema/migration)
before applying to an instance with data in it.

> Docs:
> [Create and load a schema](https://docs.infrahub.app/schema/create-and-load)
> · [Schema migrations](https://docs.infrahub.app/schema/migration)
> · [`infrahubctl schema`](https://docs.infrahub.app/infrahubctl/infrahubctl-schema)

## A word on scope

Every node you add is a node someone maintains, appears
in menus, and has to be populated for the data to mean
anything. Convert the gaps you have a use for. A
console-port node with no cable model and no query
using it is documentation with extra steps — the
report will keep telling you it was skipped, and that
is a perfectly good permanent answer.
