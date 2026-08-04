---
name: infrahub-converting-netbox-device-types
description: >-
  Converts NetBox device-type and module-type definitions (the netbox-community
  devicetype-library format, also published via the NetBox Data Exchange / NDX)
  into Infrahub object templates as Infrahub object YAML, using a bundled Python
  converter driven by a schema mapping profile.
  TRIGGER when: importing NetBox device types or module types into Infrahub,
  converting devicetype-library YAML, building object templates from vendor
  device models, seeding Infrahub with device types from NDX, converting line
  cards / PSUs / transceivers from NetBox module types, turning NetBox hardware
  definitions into Template* objects.
  DO NOT TRIGGER when: importing CSV/TSV data (use infrahub-importing-data),
  authoring schemas from scratch (use infrahub-managing-schemas), writing ordinary
  object data files (use infrahub-managing-objects), or syncing live NetBox
  instances (that is infrahub-sync, a separate product).
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
argument-hint: "[netbox-device-type-path...]"
metadata:
  version: 1.2.8
  author: OpsMill
---

# NetBox Device Type Converter

## Overview

Turns NetBox device-type YAML — the format used by
[netbox-community/devicetype-library](https://github.com/netbox-community/devicetype-library)
and browsable at the [NetBox Data Exchange](https://netboxlabs.com/ndx/)
— into Infrahub **object templates**: reusable
blueprints that create a device with all its ports
already in place.

The conversion is done by a bundled Python script,
not by hand. Hand-converting a 48-port switch means
transcribing 48 near-identical blocks, and the
library has thousands of device types. The script is
exact and repeatable; this skill is about pointing it
at the right schema and reading what it tells you.

## Project Context

Target schema files:
!`find . -name "*.yml" -path "*schema*" 2>/dev/null | head -10`

Existing mapping profiles:
!`find . -name "*.yml" -path "*mappings*" 2>/dev/null | head -10`

## When to Use

- Seeding a new Infrahub instance with vendor device
  models from the NetBox library
- Converting a handful of device types for a specific
  project or lab topology
- Re-running a conversion after the upstream library
  or the local schema changed
- Building the mapping profile that binds NetBox
  fields to a custom Infrahub schema

Not for syncing a **live** NetBox instance into
Infrahub — that is
[infrahub-sync](https://docs.infrahub.app/sync/),
a separate product. This skill converts the static
YAML definitions.

## The Shape of the Conversion

One NetBox file becomes **three** Infrahub artifacts,
because Infrahub splits what NetBox keeps together:

| NetBox | Infrahub | Why |
| ------ | -------- | --- |
| `manufacturer: Cisco` | `OrganizationManufacturer` object | Manufacturers are first-class objects |
| `model`, `part_number`, `u_height`, `weight` | `DcimDeviceType` object | Templates hold no model data |
| `interfaces:` and other component lists | `TemplateDcimDevice` + component templates | The reusable blueprint |

The template links to the device type, so creating a
device from the template also wires up its model.

**Module types** are a second input family — line
cards, PSUs, and transceivers, in a sibling
`module-types/` directory. They carry no `slug`, which
is how the converter tells the two apart, so a mixed
tree converts in one pass. They follow the same split
(a module type object, optionally a module template)
and land in `04_module_types.yml` /
`05_module_templates.yml`. Read
[extending-your-schema.md](./extending-your-schema.md#converting-module-types)
before promising much here: against the stock
schema-library a module type has **no component
relationships**, so its ports do not convert.

Module port names carry NetBox's `{module}` token, which
no conversion can resolve — the bay position is only
known once the module is installed. Once the
schema-library module extensions are loaded so the ports
import as `DeviceModulePort` declarations, the bundled
generator resolves the token per installed module and
creates the real device interfaces. See
[generators-module-ports.md](./generators-module-ports.md).

Three facts drive almost every surprise in this
workflow — explain them rather than assuming them:

1. **`Template*` kinds are generated, not written.**
   `generate_template: true` on a node creates them;
   without it they do not exist.
2. **Component templates come only from `Component`
   relationships.** An `Attribute` relationship keeps
   pointing at real objects.
3. **Model data lives on the device type, not the
   template.** That is why three files, in that order.

New to Infrahub's data model, or explaining it to
someone who is? [concepts.md](./concepts.md) covers
these with links to the Infrahub docs.

## Rule Categories

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Workflow | `workflow-` | `generate_template` must be enabled first |
| CRITICAL | Mapping | `mapping-` | Names come from the schema, never guessed; competing fields declare precedence |
| CRITICAL | Format | `format-` | Envelope, `Template<Kind>`, nested components |
| HIGH | Naming | `naming-` | Slug-based, parent-namespaced, unique |
| HIGH | Coverage | `coverage-` | Report what did not convert |
| MEDIUM | Output | `output-` | Three files, load order, branch-first |

Full index: [rules/_sections.md](./rules/_sections.md).

## Workflow

### 1. Confirm the schema generates templates

`Template*` kinds exist only where a node declares
`generate_template: true`. In the OpsMill
schema-library that line ships **commented out** in
`base/dcim.yml`, so this is the most common reason a
conversion loads nothing.

Read
[rules/workflow-schema-prerequisites.md](./rules/workflow-schema-prerequisites.md).

If it is not enabled, **explain the change rather than
making it silently**: the flag generates
`TemplateDcimDevice` plus a component template for
every `Component` relationship, it is additive, and the
schema has to be reloaded for the kinds to appear.
Enabling it touches the user's source of truth, so it
is their call — show the one-line diff and let them
decide.

> Docs:
> [Object Templates overview](https://docs.infrahub.app/object-templates/overview)
> · [Create and load a schema](https://docs.infrahub.app/schema/create-and-load)

### 2. Choose or write a mapping profile

The converter binds NetBox fields to Infrahub
attributes through a profile, so it never guesses a
name.

- Using the OpsMill schema-library? Start with
  `scripts/mappings/schema-library.yml`, or
  `scripts/mappings/schema-library-modules.yml` if you
  also want module types.
- Custom schema? Copy `scripts/mappings/_template.yml`
  and fill it in **by reading the schema YAML**, kind
  by kind and attribute by attribute.

Read
[rules/mapping-profile-driven.md](./rules/mapping-profile-driven.md)
and [reference.md](./reference.md) for the full field
inventory on both sides. Where two NetBox fields
compete for one Infrahub attribute — `description` vs
`comments`, interface `label` vs `description` —
declare precedence with `fallback` rather than
picking one and losing the other; see
[rules/mapping-fallback-sources.md](./rules/mapping-fallback-sources.md).

**Check for a node that already covers a gap before
concluding one is missing.** A console port is often
modelled as a node inheriting the interface generic, in
which case it rides the device's existing `interfaces`
relationship and needs no schema change at all — only
a profile entry. When two lists share one relationship,
read
[rules/mapping-shared-relationships.md](./rules/mapping-shared-relationships.md):
getting that wrong discards the larger list silently.
[extending-your-schema.md](./extending-your-schema.md)
lists what schema-library and infrahub-demo-dc already
provide.

### 3. Get the input

The library is a git repo; NDX is its browsable front
end. There is no public bulk API, so clone it — but
sparsely. A plain `--depth 1` clone pulls 1.6 GB,
almost all of it rack elevation images the converter
never reads. Restricting to `device-types/` gets the
same 5,900+ definitions in 29 MB:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/netbox-community/devicetype-library.git
cd devicetype-library
git sparse-checkout set device-types module-types
```

Drop `module-types` from that list if you only want
devices.

The converter accepts files, directories (walked
recursively), and globs.

### 4. Run the converter

```bash
python skills/infrahub-converting-netbox-device-types/scripts/netbox_to_infrahub_templates.py \
  devicetype-library/device-types/Cisco/ \
  --mapping skills/infrahub-converting-netbox-device-types/scripts/mappings/schema-library.yml \
  --output-dir ./generated \
  --report ./generated/coverage-report.md
```

Exit codes: `0` converted, `1` bad profile or
malformed input, `2` no files matched.

### 5. Read the coverage report, explain the loss, offer the fix

Against a typical schema, a large part of each NetBox
file has nowhere to go. Open the report and, in the
response:

1. **Name the biggest losses** — which component lists
   and which fields, with counts. Do not just say a
   report exists.
2. **Explain why the schema could not hold them.**
   "Skipped `console-ports`" is unactionable to someone
   who does not know component templates come only from
   `Component` relationships. Give the reason.
3. **Offer the concrete fix.** A dropped field is one
   attribute; a skipped list is a node plus a
   Component/Parent pair. Both are additive.
   [extending-your-schema.md](./extending-your-schema.md)
   has worked YAML per case, including which
   schema-library extensions already cover some of them.

Offer — do not unilaterally rewrite their schema. It is
a migration against their source of truth.

Read
[rules/coverage-report-unmapped.md](./rules/coverage-report-unmapped.md).

Two cases worth flagging by name when they apply:

- **Modular chassis convert to an empty template** —
  their ports live in module bays, 13.5% of the
  published library. The schema-library modules
  extension does not close this the way it looks like it
  should; see
  [extending-your-schema.md](./extending-your-schema.md#module-bays-what-the-modules-extension-does-and-does-not-give-you).
- **Console ports are usually a profile change, not a
  schema change** — if the schema models them as a node
  inheriting the interface generic, they already ride
  the `interfaces` relationship.

### 6. Load onto a branch

```bash
infrahubctl branch create netbox-import
for file in generated/0*.yml; do
  infrahubctl object load "$file" --branch netbox-import
done
```

Load order is dependency order — manufacturers, then
device types, then templates. Read
[rules/output-load-order.md](./rules/output-load-order.md).
Never load a bulk import straight to the default
branch.

## Extending the Converter

Reach for the mapping profile first — it covers new
kinds, renamed attributes, extra component lists, and
conditional values without touching Python. Change the
script only for a genuinely new *mechanism* (a
transform kind that does not exist yet). Adding a
schema-specific special case to the script is how it
stops working for everyone else.

Its tests live at
`tests/scripts/test_netbox_to_infrahub_templates.py`;
run them after any change.

## Supporting References

| File | Read it when |
| ---- | ------------ |
| [concepts.md](./concepts.md) | The Infrahub model is unfamiliar, or you need to explain it |
| [extending-your-schema.md](./extending-your-schema.md) | Turning a reported gap into a schema change |
| [generators-module-ports.md](./generators-module-ports.md) | Module ports imported as declarations and the `{module}` token needs resolving into real device interfaces |
| [reference.md](./reference.md) | Looking up a NetBox field or its Infrahub counterpart |
| [examples.md](./examples.md) | Needing a worked conversion, profile, or schema patch |
| [rules/](./rules/) | Applying or checking a specific rule |
| [../infrahub-managing-objects/rules/value-profiles-templates.md](../infrahub-managing-objects/rules/value-profiles-templates.md) | Authoring templates by hand, or choosing profiles vs templates |
| [../infrahub-managing-schemas/rules/relationship-component-parent.md](../infrahub-managing-schemas/rules/relationship-component-parent.md) | Adding the component relationships templates are generated from |

## Infrahub Documentation

Link these when explaining a concept — a user who
follows one link learns the feature, not just this
conversion.

| Topic | Page |
| ----- | ---- |
| What object templates are | <https://docs.infrahub.app/object-templates/overview> |
| Enabling and using them | <https://docs.infrahub.app/object-templates/use> |
| Templates plus Profiles | <https://docs.infrahub.app/object-templates/with-profiles> |
| Per-object unique values | <https://docs.infrahub.app/object-templates/allocate-resources-from-pools> |
| Nodes and attributes | <https://docs.infrahub.app/schema/nodes-and-attributes> |
| Relationships (Component vs Attribute) | <https://docs.infrahub.app/schema/relationships> |
| Generics and inheritance | <https://docs.infrahub.app/schema/generics-and-inheritance> |
| Extending a schema without forking it | <https://docs.infrahub.app/schema/extensions> |
| Loading a schema | <https://docs.infrahub.app/schema/create-and-load> |
| Schema migrations and their risks | <https://docs.infrahub.app/schema/migration> |
| Schema property reference | <https://docs.infrahub.app/reference/schema/node> |
| Profiles vs templates | <https://docs.infrahub.app/profiles/overview> |
| Schema from scratch (tutorial) | <https://docs.infrahub.app/academy/tutorials/build-your-first-schema> |
| Generators (resolving `{module}` after install) | <https://docs.infrahub.app/generators/overview> |
