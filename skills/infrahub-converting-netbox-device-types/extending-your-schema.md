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
  ports. If you convert chassis (13.5% of the library
  produce an empty template without this), you likely
  want NetBox *module types* too — a separate input
  format this converter does not read.

Before adding all nine, check whether the schema-library
already has an extension covering it:

```bash
ls schema-library/extensions/
```

`modules/`, `patch_panel/`, and `sfp/` overlap with
several of the rows above.

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
