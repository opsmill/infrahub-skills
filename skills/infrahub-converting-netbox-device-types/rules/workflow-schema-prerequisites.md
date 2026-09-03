---
title: Schema Prerequisites for Object Templates
impact: CRITICAL
tags: workflow, schema, generate_template, templates
---

## Schema Prerequisites for Object Templates

Impact: CRITICAL

`Template<Kind>` nodes do not exist until the target
node carries `generate_template: true` and the schema
is loaded. Confirm that before converting anything.

### Why it matters

Object templates are *generated* kinds, not
hand-written ones. Infrahub creates `TemplateDcimDevice`
only because `DcimDevice` declares
`generate_template: true`; it creates
`TemplateInterfacePhysical` only because
`DcimDevice` reaches `InterfacePhysical` through a
`Component` relationship. Convert first and you get a
directory of YAML referencing kinds the server has
never heard of — every file fails to load with
"schema kind not found", and the failure appears at
load time, far from the conversion that caused it.

Which side of this a schema-library project falls on
depends on its version, so check rather than assume:
**v2 and later enable it** on `DcimDevice`, while
pre-v2 shipped `base/dcim.yml` with the line
**commented out**. A schema pinned to the older
library, or any custom schema, still needs it added.

> Docs:
> [Object Templates overview](https://docs.infrahub.app/object-templates/overview)
> · [Use object templates](https://docs.infrahub.app/object-templates/use)

### What to check

1. The device node has `generate_template: true`. It
   is a **node** property — setting it on a generic
   does nothing.
2. The components you intend to convert are reachable
   via a `Component` relationship from that node.
   Templates are generated for component relationships
   only; an `Attribute` relationship keeps pointing at
   real objects, not templates.
3. The schema has been loaded, so the generated kinds
   exist.

**Not template-generating:**

```yaml
nodes:
  - name: Device
    namespace: Dcim
    # generate_template: true    # pre-v2 schema-library — no Template* kinds
```

**Template-generating:**

```yaml
nodes:
  - name: Device
    namespace: Dcim
    generate_template: true      # generates TemplateDcimDevice
    relationships:
      - name: interfaces
        peer: DcimInterface
        kind: Component          # generates TemplateDcimInterface
```

Load the schema onto a branch and verify the generated
kinds exist before converting:

```bash
infrahubctl branch create netbox-import
infrahubctl schema load schemas/dcim.yml --branch netbox-import
```

### Explain the change, do not just make it

Enabling `generate_template` is a schema change on the
user's source of truth, so it is their call. When it
is missing, say what the flag does, what it generates,
and that the schema must be reloaded — rather than
silently adding a line or converting into a void:

> `DcimDevice` does not have `generate_template: true`,
> so `TemplateDcimDevice` and `TemplateInterfacePhysical`
> do not exist yet and the converted files cannot load.
> Adding that one line to the node and reloading the
> schema generates both. It is additive and does not
> affect existing devices.

If a component you need is not reachable via a
`Component` relationship, that is a larger schema
change — point at
[../extending-your-schema.md](../extending-your-schema.md)
rather than guessing at the shape.

### Common mistakes

- **Putting `generate_template` on a generic.** It is
  ignored there; only nodes generate templates.
- **Expecting model data on the template.** A template
  holds no `height`, `part_number`, or `weight` —
  those live on the device type object the template
  links to. That split is why the converter emits both.
  Background: [../concepts.md](../concepts.md).
- **Assuming every relationship becomes a template.**
  Only `Component` relationships do. An `Attribute`
  relationship keeps pointing at real objects.
- **Expecting a template edit to update existing
  devices.** Templates apply at creation time and are
  not retroactive.
