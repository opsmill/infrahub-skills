# Examples

Three worked conversions, from the simplest case to a
schema extension that closes a coverage gap.

## 1. A single switch against the schema-library

### Input — `device-types/Cisco/C9300-48P.yaml` (abridged)

```yaml
---
manufacturer: Cisco
model: Catalyst 9300-48P
part_number: C9300-48P
slug: cisco-c9300-48p
u_height: 1
is_full_depth: true
weight: 7.59
weight_unit: kg
airflow: front-to-rear
console-ports:
  - name: con 0
    type: rj-45
interfaces:
  - name: GigabitEthernet1/0/1
    type: 1000base-t
    poe_mode: pse
    poe_type: type2-ieee802.3at
  - name: GigabitEthernet1/0/48
    type: 1000base-t
```

### Schema prerequisite

`DcimDevice` needs `generate_template: true`.
schema-library **v2 and later already set it**; on a
pre-v2 pin it ships commented out and has to be
uncommented and the schema reloaded:

```yaml
  - name: Device
    namespace: Dcim
    generate_template: true    # set on v2; uncomment on pre-v2
    inherit_from:
      - CoreArtifactTarget
      - DcimGenericDevice
      - DcimPhysicalDevice
```

That one line generates `TemplateDcimDevice`, plus
`TemplateInterfacePhysical` for the inherited
`interfaces` Component relationship.

### Command

```bash
python scripts/netbox_to_infrahub_templates.py \
  device-types/Cisco/C9300-48P.yaml \
  --mapping scripts/mappings/schema-library.yml \
  --output-dir ./generated
```

### Output — `generated/01_manufacturers.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: OrganizationManufacturer
  data:
  - name: Cisco
```

### Output — `generated/02_device_types.yml`

The model data lands here, not on the template.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDeviceType
  data:
  - name: Catalyst 9300-48P
    part_number: C9300-48P
    height: 1
    full_depth: true
    weight: 8
    manufacturer: Cisco
```

### Output — `generated/03_device_templates.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: TemplateDcimDevice
  data:
  - template_name: cisco-c9300-48p
    device_type: Catalyst 9300-48P
    status: active
    interfaces:
      kind: TemplateInterfacePhysical
      data:
      - template_name: cisco-c9300-48p__GigabitEthernet1/0/1
        name: GigabitEthernet1/0/1
        status: active
      - template_name: cisco-c9300-48p__GigabitEthernet1/0/48
        name: GigabitEthernet1/0/48
        status: active
```

### Output — `generated/coverage-report.md`

```markdown
### `cisco-c9300-48p`

- Skipped `console-ports` (1 entry) — not mapped by the profile
- Dropped from `device_type`: `airflow`
- Dropped from `interfaces`: `poe_mode`, `poe_type`, `type`
```

Say this out loud when handing over: *the console port
and every interface's media type did not survive.*

### Load

```bash
infrahubctl branch create netbox-import
for file in generated/0*.yml; do
  infrahubctl object load "$file" --branch netbox-import
done
```

### Using the result

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: leaf-01
      object_template: cisco-c9300-48p   # 48 interfaces created with it
      serial: FCW2140L0GH                # per-instance detail
```

## 2. A whole vendor directory

Clone sparsely — the elevation images make a full
clone 1.6 GB, against 29 MB for the definitions alone.

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/netbox-community/devicetype-library.git
cd devicetype-library && git sparse-checkout set device-types && cd ..

python scripts/netbox_to_infrahub_templates.py \
  devicetype-library/device-types/Juniper/ \
  --mapping scripts/mappings/schema-library.yml \
  --output-dir ./generated \
  --report ./generated/coverage-report.md
```

Manufacturers are de-duplicated across the batch, and
a template-name collision aborts the run rather than
producing YAML that half-loads:

```text
error: device-types/Juniper/EX4300-48T.yaml: template_name
'juniper-ex4300-48t' already produced by
device-types/Juniper/EX4300-48T-copy.yaml; template names must be unique
```

Weight conversion shows up in the report:

```markdown
- Coerced weight: weight 16.1 lb converted to 7 kg
```

## 3. Closing a coverage gap

Console ports are skipped because schema-library has
no node for them. Closing that gap is a schema change
plus a profile change — both, or neither.

This is one worked case;
[extending-your-schema.md](./extending-your-schema.md)
covers all nine NetBox component lists, the
dropped-attribute case (`interfaces.type`), and the
shadowed-value case.

### Schema — add the node and the Component relationship

```yaml
---
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
    relationships:
      - name: device
        peer: DcimGenericDevice
        identifier: device__consoleport
        optional: false
        cardinality: one
        kind: Parent          # the Component/Parent pair is what
        order_weight: 1050    # generates TemplateDcimConsolePort

extensions:
  nodes:
    - kind: DcimGenericDevice
      relationships:
        - name: console_ports
          peer: DcimConsolePort
          identifier: device__consoleport   # must match the Parent side
          optional: true
          cardinality: many
          kind: Component
          order_weight: 1800
```

### Profile — add the list

```yaml
components:
  interfaces:
    kind: TemplateInterfacePhysical
    relationship: interfaces
    template_name: "{template_name}__{name}"
    fields:
      name: name

  console-ports:
    kind: TemplateDcimConsolePort
    relationship: console_ports        # the Component relationship name
    template_name: "{template_name}__console__{name}"
    fields:
      name: name
      type: port_type                  # only valid because the Dropdown
                                       # declares rj-45 and usb-mini-b
```

### Re-run

```bash
python scripts/netbox_to_infrahub_templates.py \
  device-types/Cisco/C9300-48P.yaml \
  --mapping scripts/mappings/my-schema.yml \
  --output-dir ./generated
```

```yaml
    console_ports:
      kind: TemplateDcimConsolePort
      data:
      - template_name: cisco-c9300-48p__console__con 0
        name: con 0
        port_type: rj-45
```

The report now lists `console-ports` under converted
components instead of skipped ones.

Note the two traps this example avoids: the
`identifier` matches on both sides of the
Component/Parent pair, and `type: port_type` is only
mappable because every NetBox value in the input has a
matching Dropdown choice. Map a NetBox `type` onto a
Dropdown missing that choice and the load fails — leave
it unmapped and reported instead.
