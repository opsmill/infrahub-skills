# Reference

## NetBox device-type fields

Source of truth: the definitions schema in
[netbox-community/devicetype-library](https://github.com/netbox-community/devicetype-library).

### Top level

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `manufacturer` | string | yes | Becomes its own Infrahub object |
| `model` | string | yes | The device type name |
| `slug` | string | yes | `^[-a-z0-9_]+$`, unique library-wide — the template key |
| `part_number` | string | no | Vendor ordering code |
| `u_height` | number | no | Multiples of 0.5; Infrahub `Number` attributes take integers |
| `is_full_depth` | boolean | no | Defaults to true |
| `airflow` | string | no | `front-to-rear`, `rear-to-front`, `left-to-right`, `right-to-left`, `side-to-rear`, `rear-to-side`, `bottom-to-top`, `top-to-bottom`, `passive`, `mixed` |
| `weight` | number | no | Paired with `weight_unit` |
| `weight_unit` | string | no | `kg`, `g`, `lb`, `oz` |
| `subdevice_role` | string | no | `parent` or `child` |
| `is_powered` | boolean | no | Defaults to true |
| `front_image` / `rear_image` | boolean | no | Whether an elevation image exists |
| `comments` | string | no | Usually a Markdown datasheet link |

### Component lists

| List | Entry fields |
| ---- | ------------ |
| `console-ports` | `name`, `label`, `type` |
| `console-server-ports` | `name`, `label`, `type` |
| `power-ports` | `name`, `label`, `type`, `maximum_draw`, `allocated_draw` |
| `power-outlets` | `name`, `label`, `type`, `power_port`, `feed_leg` |
| `interfaces` | `name`, `label`, `type`, `mgmt_only`, `poe_mode`, `poe_type` |
| `front-ports` | `name`, `label`, `type`, `rear_port`, `rear_port_position` |
| `rear-ports` | `name`, `label`, `type`, `positions` |
| `module-bays` | `name`, `label`, `position` |
| `device-bays` | `name`, `label` |
| `inventory-items` | `name`, `label`, `manufacturer`, `part_id` |

## NetBox module-type fields

A second input family, in a sibling `module-types/`
directory. Told apart from device types by carrying no
`slug`.

| Field | Required | Notes |
| ----- | -------- | ----- |
| `manufacturer` | yes | 100% of published module types |
| `model` | yes | Unique across all 1,909; stands in for the missing slug |
| `part_number` | no | 93.8% |
| `comments` | no | 68.6%, usually a datasheet link |
| `description` | no | 29.0% |
| `weight` / `weight_unit` | no | 23.0% |
| `airflow` | no | 4.3% |
| `profile` / `attribute_data` | no | NetBox module-type profiles; 4.2% / 2.4% |

Component lists, by share of files: `interfaces`
(41.7%), `power-ports` (35.4%), `rear-ports` (9.1%),
`front-ports` (8.4%), `console-ports` (5.3%),
`module-bays` (1.1%), `console-server-ports` (0.5%).

**93.9% of component names contain `{module}`**, the
bay-position token NetBox substitutes at install time.
See `module_type.position_placeholder`.

## Infrahub object templates

| Concept | Detail |
| ------- | ------ |
| Generated kind | `Template` + the node kind — `DcimDevice` becomes `TemplateDcimDevice` |
| Enabled by | `generate_template: true` on the **node** (not on a generic) |
| Identity attribute | `template_name`, unique per kind, and the `human_friendly_id` |
| Component templates | Generated for `Component` relationships only |
| Model data | Not on the template — on the device type object it links to |
| Unique attributes | **Omitted from the template entirely**, which is why a node with a unique identity is still templatable |
| Creating from one | Set `object_template: <template_name>` on the object |
| Retroactivity | None; editing a template does not change objects already created from it |

Docs:
[Object Templates overview](https://docs.infrahub.app/object-templates/overview),
[Use object templates](https://docs.infrahub.app/object-templates/use).

## Default profile mapping (schema-library)

What `scripts/mappings/schema-library.yml` binds, and
what it cannot.

### Mapped

| NetBox | Infrahub | Transform |
| ------ | -------- | --------- |
| `manufacturer` | `OrganizationManufacturer.name` | — |
| `model` | `DcimDeviceType.name` | — |
| `part_number` | `DcimDeviceType.part_number` | — |
| `description`, else `comments` | `DcimDeviceType.description` | fallback |
| `u_height` | `DcimDeviceType.height` | `number` |
| `is_full_depth` | `DcimDeviceType.full_depth` | `boolean` |
| `weight` + `weight_unit` | `DcimDeviceType.weight` | `weight_kg` |
| `slug` | `TemplateDcimDevice.template_name` | format string |
| `interfaces[].name` | `TemplateInterfacePhysical.name` | — |
| `interfaces[].description`, else `.label` | `TemplateInterfacePhysical.description` | fallback |
| `interfaces[].mgmt_only: true` | `role: management` | derived |

### Not mapped — reported as skipped

`console-ports`, `console-server-ports`,
`power-ports`, `power-outlets`, `front-ports`,
`rear-ports`, `module-bays`, `device-bays`,
`inventory-items` — schema-library models no
equivalent node.

### Not mapped — reported as dropped

`airflow`, `subdevice_role`, `is_powered`,
`front_image`, `rear_image`, and per interface
`type`, `poe_mode`, `poe_type` — the attributes do
not exist on the target kinds. `InterfacePhysical` in
particular has no media-type or PoE attribute.

### Mapped but shadowed

Where a fallback is declared and *both* sources carry
a value, the loser is reported as shadowed. In the
published library that is `comments` on 188 device
types and interface `label` on 206 entries.

## Mapping profile keys

| Key | Required | Meaning |
| --- | -------- | ------- |
| `manufacturer.kind` | yes | Infrahub kind for manufacturers |
| `manufacturer.name_field` | yes | Attribute holding the manufacturer name |
| `device_type.kind` | yes | Infrahub kind for device types |
| `device_type.manufacturer_relationship` | yes | Relationship from device type to manufacturer |
| `device_type.fields` | no | NetBox field to Infrahub attribute map |
| `<field>.fallback` | no | Field name or ordered list tried when the primary source is empty |
| `device_type.defaults` | no | Attributes written on every device type |
| `template.kind` | yes | The generated `Template<Kind>` |
| `template.template_name` | yes | Format string over the NetBox top-level fields |
| `template.device_type_relationship` | yes | Relationship from device to device type |
| `template.defaults` | no | Attributes written on every template |
| `components.<list>.kind` | yes | Concrete component template kind |
| `components.<list>.relationship` | yes | Component relationship on the parent template; several lists may share one |
| `components.<list>.template_name` | yes | Format string; `{template_name}` is the parent's |
| `components.<list>.fields` | no | Per-entry field map |
| `components.<list>.derived` | no | Conditional attributes (`when` / `value`) |
| `components.<list>.defaults` | no | Attributes written on every entry |
| `module_type` | no | Enables module-type conversion; without it, module files are refused |
| `module_type.kind` | yes* | Concrete module type kind — not the generic |
| `module_type.manufacturer_relationship` | yes* | Relationship to the manufacturer |
| `module_type.key` | no | Identity format string, default `{model}` |
| `module_type.fields` | no | Field map, same syntax as `device_type.fields` |
| `module_type.position_placeholder` | no | Value substituted for `{module}`; unset keeps it literal |
| `module_type.template` | no | Enables module templates; needed before `module_type.components` |
| `module_type.components` | no | Component lists on the module template |

`yes*` = required only when a `module_type` section is present.

### Transforms

| Name | Effect |
| ---- | ------ |
| `text` | Pass through (default) |
| `number` | Coerce to a whole number, halves rounded away from zero |
| `boolean` | Coerce to bool |
| `weight_kg` | Convert using `weight_unit` into **whole kilograms** |
| `weight_g` | Convert using `weight_unit` into **whole grams** |

Every numeric transform emits an integer. Infrahub has
no float or decimal attribute kind — `Number` maps to
`graphene.BigInt` with `infrahub = "Integer"` — so a
fractional value cannot be stored, and emitting one
produces YAML that fails at load time rather than
sorting badly.

Rounding is half-away-from-zero, not Python's default
banker's rounding: `0.5` becomes `1`, not `0`.

### Choosing a weight unit

|                                     | `weight_kg` | `weight_g`                   |
| ----------------------------------- | ----------- | ---------------------------- |
| Fits schema-library's `Weight (kg)` | yes         | no — needs a grams attribute |
| Published device types rounded to 0 | **302**     | 0                            |
| Mean error under 1 kg               | 72.8%       | none                         |
| Mean error over 20 kg               | 0.6%        | none                         |

Kilograms are fine for racked equipment and destroy
sub-500g hardware. Every value that rounds to zero is
named individually in the coverage report.

## Converter CLI

```text
netbox_to_infrahub_templates.py INPUT... --mapping PROFILE --output-dir DIR
                                [--report PATH|-]
```

| Argument | Meaning |
| -------- | ------- |
| `INPUT...` | Files, directories (walked recursively), or globs |
| `--mapping` | Mapping profile YAML |
| `--output-dir` | Where the three object files are written |
| `--report` | Coverage report path; `-` writes it to stdout |

| Exit code | Meaning |
| --------- | ------- |
| 0 | Converted (possibly with skipped components) |
| 1 | Bad mapping profile, unreadable input, or malformed NetBox file |
| 2 | No input files matched |

## Output files

| File | Kind | Depends on |
| ---- | ---- | ---------- |
| `01_manufacturers.yml` | `manufacturer.kind` | — |
| `02_device_types.yml` | `device_type.kind` | manufacturers |
| `03_device_templates.yml` | `template.kind` | device types |
| `04_module_types.yml` | `module_type.kind` | manufacturers |
| `05_module_templates.yml` | `module_type.template.kind` | module types |
| `coverage-report.md` | — | — |

Files with no content are not written, so converting
only module types emits `01` and `04` alone.

### Component relationship shape

One mapping on a relationship emits a mapping; several
mappings sharing one emit a list of blocks, in profile
order. Both are valid — the object loader resolves
`kind` per item.

```yaml
interfaces:                        # one mapping
  kind: TemplateInterfacePhysical
  data: [ ... ]

interfaces:                        # two mappings sharing the relationship
  - kind: TemplateInterfacePhysical
    data: [ ... ]
  - kind: TemplateDcimConsoleInterface
    data: [ ... ]
```
